"""
SensorSimulator — 가상 센서 데이터 생성기
==========================================
각 설비(Equipment)에 온도/진동/전류 등 센서를 부착하고
주기적으로 읽기값을 생성한다. 이상(Anomaly)도 확률적으로 발생시킨다.

L2(운영) 계층 스키마 확장 함수도 포함한다.
"""

import math
import random
from datetime import datetime, timezone

# ───────────────────────────────────────────────────────────────
#  L2 Schema Extension
# ───────────────────────────────────────────────────────────────

def extend_schema_l2(conn):
    """온톨로지에 L2(운영) 계층 노드/관계를 추가한다."""

    node_tables = [
        (
            "CREATE NODE TABLE SensorReading ("
            "id STRING, step_id STRING, equip_id STRING, sensor_type STRING, "
            "value DOUBLE, unit STRING, is_anomaly BOOLEAN, timestamp STRING, "
            "PRIMARY KEY(id))"
        ),
        (
            "CREATE NODE TABLE Alarm ("
            "id STRING, step_id STRING, severity STRING, sensor_type STRING, "
            "value DOUBLE, message STRING, timestamp STRING, "
            "resolved BOOLEAN DEFAULT false, PRIMARY KEY(id))"
        ),
        (
            "CREATE NODE TABLE Incident ("
            "id STRING, step_id STRING, alarm_id STRING, root_cause STRING, "
            "recovery_action STRING, resolved BOOLEAN DEFAULT false, "
            "auto_recovered BOOLEAN DEFAULT false, timestamp STRING, "
            "PRIMARY KEY(id))"
        ),
        (
            "CREATE NODE TABLE RecoveryAction ("
            "id STRING, incident_id STRING, action_type STRING, parameter STRING, "
            "old_value DOUBLE, new_value DOUBLE, success BOOLEAN, timestamp STRING, "
            "PRIMARY KEY(id))"
        ),
    ]

    rel_tables = [
        "CREATE REL TABLE HAS_READING (FROM Equipment TO SensorReading)",
        "CREATE REL TABLE TRIGGERED_BY (FROM Alarm TO SensorReading)",
        "CREATE REL TABLE HAS_ALARM (FROM ProcessStep TO Alarm)",
        "CREATE REL TABLE HAS_INCIDENT (FROM ProcessStep TO Incident)",
        "CREATE REL TABLE RESOLVED_BY (FROM Incident TO RecoveryAction)",
        "CREATE REL TABLE CAUSED_BY (FROM Incident TO DefectMode)",
    ]

    for ddl in node_tables + rel_tables:
        try:
            conn.execute(ddl)
        except Exception:
            pass  # 이미 존재하면 무시


# ───────────────────────────────────────────────────────────────
#  Equipment-type sensor profiles
# ───────────────────────────────────────────────────────────────

# 키워드 패턴 → 센서 정의 목록
# 각 항목: (sensor_type, unit, normal_min, normal_max)
_SENSOR_PROFILES = [
    # 용접 계열
    (["용접", "레이저"], [
        ("temperature", "°C", 200.0, 400.0),
        ("current",     "A",  80.0,  200.0),
    ]),
    # CNC/가공 계열
    (["CNC", "가공"], [
        ("temperature", "°C",  30.0, 60.0),
        ("vibration",   "mm/s", 1.0,  3.0),
    ]),
    # 검사 계열
    (["검사", "테스터", "테스트", "AOI", "X-ray", "비전", "HiPot", "HIL"], [
        ("temperature", "°C", 20.0, 25.0),
    ]),
    # 코팅/표면처리
    (["코팅", "표면", "에폭시"], [
        ("temperature", "°C", 22.0, 28.0),
        ("temperature_proxy_humidity", "°C", 22.0, 28.0),
    ]),
    # 조립 계열
    (["조립", "체결", "렌치", "압착", "부착"], [
        ("temperature",  "°C", 20.0, 30.0),
        ("torque_force", "Nm", 20.0, 40.0),
    ]),
    # 로봇 계열
    (["로봇", "KUKA", "인서트 로봇"], [
        ("temperature", "°C",   25.0, 45.0),
        ("current",     "A",    30.0, 80.0),
        ("vibration",   "mm/s",  0.5,  2.0),
    ]),
]

# 기본 프로파일 (어디에도 해당 안 되면)
_DEFAULT_PROFILE = [
    ("temperature", "°C",   20.0, 35.0),
    ("vibration",   "mm/s",  0.5,  3.0),
]


def _match_profile(equip_name: str) -> list:
    """설비 이름에서 키워드를 매칭하여 센서 프로파일을 반환한다."""
    for keywords, profile in _SENSOR_PROFILES:
        for kw in keywords:
            if kw in equip_name:
                return profile
    return _DEFAULT_PROFILE


def _cost_adjusted_current_range(equip_cost: int):
    """설비 원가 기반으로 전류 센서 범위를 보정한다. (고가 장비 = 높은 전류)"""
    base_min = 10.0 + equip_cost / 50000
    base_max = base_min + 40.0 + equip_cost / 25000
    return (round(base_min, 1), round(base_max, 1))


# ───────────────────────────────────────────────────────────────
#  SensorSimulator
# ───────────────────────────────────────────────────────────────

class SensorSimulator:
    """가상 센서 데이터 생성기. 각 설비에 온도/진동/전류 센서를 부착하고 주기적으로 값을 생성한다."""

    def __init__(self, conn, anomaly_probability: float = 0.05):
        """
        Parameters
        ----------
        conn : kuzu.Connection
            그래프 DB 연결 객체.
        anomaly_probability : float
            각 읽기값이 이상치(anomaly)가 될 확률 (0.0-1.0). 기본 5%.
        """
        self.conn = conn
        self.anomaly_probability = anomaly_probability

        # step_id -> {equip_id, equip_name, equip_cost}
        self._step_equip = {}
        # list of sensor definitions:
        #   {sensor_id, step_id, equip_id, sensor_type, unit, normal_min, normal_max}
        self.sensors = []

        # 강제 이상 주입 큐: {(step_id, sensor_type): severity}
        self._forced_anomalies = {}

        self._load_equipment()

    # ── DB에서 공정/설비 로드 ─────────────────────────────────

    def _load_equipment(self):
        """ProcessStep → Equipment 관계를 쿼리해 센서를 정의한다."""
        result = self.conn.execute(
            "MATCH (ps:ProcessStep)-[:USES_EQUIPMENT]->(eq:Equipment) "
            "RETURN ps.id, eq.id, eq.name, eq.cost"
        )
        sensor_counter = 0
        seen_equip = set()

        while result.has_next():
            row = result.get_next()
            step_id, equip_id, equip_name, equip_cost = (
                row[0], row[1], row[2], int(row[3])
            )

            self._step_equip[step_id] = {
                "equip_id": equip_id,
                "equip_name": equip_name,
                "equip_cost": equip_cost,
            }

            # 같은 설비가 여러 공정에 매핑될 수 있으므로, 센서는 (step,equip) 쌍으로 생성
            profile = _match_profile(equip_name)

            for sensor_type, unit, normal_min, normal_max in profile:
                # 전류 센서의 경우, 설비 원가로 범위 보정
                if sensor_type == "current" and "검사" not in equip_name:
                    adj_min, adj_max = _cost_adjusted_current_range(equip_cost)
                    # 프로파일 범위와 보정 범위의 교집합/합집합 활용
                    normal_min = max(normal_min, adj_min)
                    normal_max = max(normal_max, adj_max)

                sensor_counter += 1
                self.sensors.append({
                    "sensor_id": f"SEN-{sensor_counter:04d}",
                    "step_id": step_id,
                    "equip_id": equip_id,
                    "sensor_type": sensor_type,
                    "unit": unit,
                    "normal_min": normal_min,
                    "normal_max": normal_max,
                })

    # ── 읽기값 생성 ──────────────────────────────────────────

    def generate_readings(self) -> list:
        """
        모든 센서에서 1회 읽기값을 생성한다.

        Returns
        -------
        list[dict]
            SensorReading 딕셔너리 리스트.
        """
        now = datetime.now(timezone.utc).isoformat()
        readings = []

        for sensor in self.sensors:
            normal_min = sensor["normal_min"]
            normal_max = sensor["normal_max"]
            mid = (normal_min + normal_max) / 2.0
            # sigma: ~95% 값이 range 안에 들도록
            sigma = (normal_max - normal_min) / 4.0

            key = (sensor["step_id"], sensor["sensor_type"])
            forced_severity = self._forced_anomalies.pop(key, None)

            is_anomaly = False
            if forced_severity is not None:
                is_anomaly = True
                value = self._generate_anomaly_value(
                    mid, sigma, normal_min, normal_max, forced_severity
                )
            elif random.random() < self.anomaly_probability:
                is_anomaly = True
                # 자연 발생 이상: severity 1-2 (경미~중간)
                severity = random.choice([1, 1, 2])
                value = self._generate_anomaly_value(
                    mid, sigma, normal_min, normal_max, severity
                )
            else:
                value = random.gauss(mid, sigma)
                # 정상 범위 내로 클램핑
                value = max(normal_min, min(normal_max, value))

            readings.append({
                "sensor_id": sensor["sensor_id"],
                "step_id": sensor["step_id"],
                "equip_id": sensor["equip_id"],
                "sensor_type": sensor["sensor_type"],
                "value": round(value, 3),
                "unit": sensor["unit"],
                "timestamp": now,
                "is_anomaly": is_anomaly,
                "normal_min": normal_min,
                "normal_max": normal_max,
            })

        return readings

    @staticmethod
    def _generate_anomaly_value(mid, sigma, normal_min, normal_max, severity):
        """
        이상치 값을 생성한다.

        severity:
          1 = mild drift (범위 경계 부근, 1.0~1.3x)
          2 = significant (범위의 1.3~1.7x)
          3 = critical (범위의 1.7~2.5x)
        """
        range_width = normal_max - normal_min

        if severity == 1:
            # 경미한 이탈
            offset = range_width * random.uniform(0.5, 0.65)
        elif severity == 2:
            # 상당한 이탈
            offset = range_width * random.uniform(0.65, 0.85)
        else:
            # 치명적 이탈
            offset = range_width * random.uniform(0.85, 1.25)

        # 방향: 상한 또는 하한 쪽
        if random.random() < 0.5:
            value = normal_max + offset * random.uniform(0.5, 1.0)
        else:
            value = normal_min - offset * random.uniform(0.5, 1.0)

        # 물리적으로 음수가 되지 않도록
        return max(0.0, value)

    # ── 강제 이상 주입 ────────────────────────────────────────

    def inject_anomaly(self, step_id: str, sensor_type: str, severity: int = 2):
        """
        특정 공정 단계의 센서에 이상을 강제로 주입한다.
        다음 generate_readings() 호출 시 해당 센서에 이상값이 생성된다.

        Parameters
        ----------
        step_id : str
            공정 단계 ID (예: 'PS-104')
        sensor_type : str
            센서 타입 (예: 'temperature', 'vibration', 'current')
        severity : int
            이상 심각도 1=경미, 2=상당, 3=치명 (기본 2)
        """
        severity = max(1, min(3, severity))
        self._forced_anomalies[(step_id, sensor_type)] = severity

    # ── 알람 체크 ─────────────────────────────────────────────

    def check_alarms(self, readings: list) -> list:
        """
        읽기값 목록에서 정상 범위를 벗어난 항목을 알람으로 변환한다.

        severity 판정:
          - 범위의 2배 이상 → CRITICAL
          - 범위의 1.5배 이상 → HIGH
          - 그 외 범위 이탈 → MEDIUM

        Parameters
        ----------
        readings : list[dict]
            generate_readings()의 반환값.

        Returns
        -------
        list[dict]
            Alarm 딕셔너리 리스트.
        """
        alarms = []
        alarm_counter = 0

        for r in readings:
            value = r["value"]
            normal_min = r["normal_min"]
            normal_max = r["normal_max"]
            range_width = normal_max - normal_min

            # 범위 안이면 알람 없음
            if normal_min <= value <= normal_max:
                continue

            # 이탈 거리 계산
            if value > normal_max:
                deviation = value - normal_max
            else:
                deviation = normal_min - value

            # severity 판정
            if range_width > 0 and deviation >= range_width:
                severity = "CRITICAL"
            elif range_width > 0 and deviation >= range_width * 0.5:
                severity = "HIGH"
            else:
                severity = "MEDIUM"

            alarm_counter += 1
            alarm_id = f"ALM-{alarm_counter:04d}"

            # 알람 메시지 생성
            direction = "초과" if value > normal_max else "미달"
            message = (
                f"{r['sensor_type']} {direction}: "
                f"{value:.1f}{r['unit']} "
                f"(정상범위 {normal_min:.1f}~{normal_max:.1f}{r['unit']}, "
                f"편차 {deviation:.1f}{r['unit']})"
            )

            alarms.append({
                "alarm_id": alarm_id,
                "sensor_id": r["sensor_id"],
                "step_id": r["step_id"],
                "equip_id": r["equip_id"],
                "sensor_type": r["sensor_type"],
                "value": value,
                "threshold_min": normal_min,
                "threshold_max": normal_max,
                "severity": severity,
                "timestamp": r["timestamp"],
                "message": message,
            })

        return alarms


# ───────────────────────────────────────────────────────────────
#  Storage helpers
# ───────────────────────────────────────────────────────────────

_MAX_STORED_READINGS = 100


def store_readings(conn, readings: list, counters: dict):
    """
    센서 읽기값을 온톨로지에 저장한다. 최근 100개만 유지.

    Parameters
    ----------
    conn : kuzu.Connection
    readings : list[dict]
        SensorReading 딕셔너리 리스트.
    counters : dict
        ID 카운터 딕셔너리 (예: {"reading": 0, "alarm": 0, ...}).
    """
    for r in readings:
        counters["reading"] += 1
        rid = f"SR-{counters['reading']:06d}"

        try:
            conn.execute(
                "CREATE (sr:SensorReading {"
                "id: $id, step_id: $step_id, equip_id: $equip_id, "
                "sensor_type: $sensor_type, value: $value, unit: $unit, "
                "is_anomaly: $is_anomaly, timestamp: $ts})",
                {
                    "id": rid,
                    "step_id": r["step_id"],
                    "equip_id": r["equip_id"],
                    "sensor_type": r["sensor_type"],
                    "value": r["value"],
                    "unit": r["unit"],
                    "is_anomaly": r["is_anomaly"],
                    "ts": r["timestamp"],
                },
            )
            # Equipment → SensorReading 관계
            conn.execute(
                "MATCH (eq:Equipment), (sr:SensorReading) "
                "WHERE eq.id = $eid AND sr.id = $rid "
                "CREATE (eq)-[:HAS_READING]->(sr)",
                {"eid": r["equip_id"], "rid": rid},
            )
        except Exception:
            pass  # 저장 실패 시 무시하고 계속

    # 최근 100개만 유지 — 오래된 읽기값 삭제
    try:
        result = conn.execute(
            "MATCH (sr:SensorReading) RETURN count(sr)"
        )
        if result.has_next():
            total = result.get_next()[0]
            if total > _MAX_STORED_READINGS:
                excess = total - _MAX_STORED_READINGS
                conn.execute(
                    "MATCH (sr:SensorReading) "
                    "WITH sr ORDER BY sr.timestamp ASC LIMIT $limit "
                    "DETACH DELETE sr",
                    {"limit": excess},
                )
    except Exception:
        pass


def store_alarm(conn, alarm: dict, counters: dict):
    """
    알람을 온톨로지에 저장하고 관련 공정에 연결한다.

    Parameters
    ----------
    conn : kuzu.Connection
    alarm : dict
        Alarm 딕셔너리.
    counters : dict
        ID 카운터 딕셔너리.
    """
    counters["alarm"] += 1
    aid = f"ALM-{counters['alarm']:06d}"

    try:
        conn.execute(
            "CREATE (a:Alarm {"
            "id: $id, step_id: $step_id, severity: $severity, "
            "sensor_type: $sensor_type, value: $value, "
            "message: $message, timestamp: $ts, resolved: false})",
            {
                "id": aid,
                "step_id": alarm["step_id"],
                "severity": alarm["severity"],
                "sensor_type": alarm["sensor_type"],
                "value": alarm["value"],
                "message": alarm["message"],
                "ts": alarm["timestamp"],
            },
        )

        # ProcessStep → Alarm 관계
        conn.execute(
            "MATCH (ps:ProcessStep), (a:Alarm) "
            "WHERE ps.id = $sid AND a.id = $aid "
            "CREATE (ps)-[:HAS_ALARM]->(a)",
            {"sid": alarm["step_id"], "aid": aid},
        )

        # Alarm → SensorReading 관계 (sensor_id 기반으로 가장 최근 읽기값 연결)
        if alarm.get("sensor_id"):
            try:
                conn.execute(
                    "MATCH (a:Alarm), (sr:SensorReading) "
                    "WHERE a.id = $aid AND sr.equip_id = $eid "
                    "AND sr.sensor_type = $stype "
                    "WITH a, sr ORDER BY sr.timestamp DESC LIMIT 1 "
                    "CREATE (a)-[:TRIGGERED_BY]->(sr)",
                    {
                        "aid": aid,
                        "eid": alarm["equip_id"],
                        "stype": alarm["sensor_type"],
                    },
                )
            except Exception:
                pass

    except Exception:
        pass

    return aid
