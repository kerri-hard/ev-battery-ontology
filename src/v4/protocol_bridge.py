"""
Protocol Bridge — 산업 프로토콜 추상화 계층
=============================================
업계 사례:
  - Siemens Insights Hub: OPC-UA → 클라우드 → AI 모델
  - PTC ThingWorx + Kepware: OPC-UA/MQTT 브릿지 → IoT 플랫폼
  - ABB Ability: MQTT + Sparkplug B → 에지 → 클라우드

현재 시스템은 SensorSimulator(가상 데이터)만 지원한다.
이 모듈은 실제 산업 프로토콜을 위한 추상화 계층을 제공하여,
시뮬레이션 → 실제 공장 전환을 최소 코드 변경으로 가능하게 한다.

지원 프로토콜:
  1. SimulatedBridge — 기존 SensorSimulator 래핑 (기본값)
  2. MQTTBridge — MQTT 브로커 연동 (paho-mqtt)
  3. OPCUABridge — OPC-UA 서버 연동 (asyncua) [인터페이스만]

사용법:
    bridge = create_bridge("mqtt", broker="localhost", port=1883)
    bridge.connect()
    readings = bridge.poll()
"""
from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable

# 선택적 의존성
try:
    import paho.mqtt.client as mqtt
    HAS_PAHO = True
except ImportError:
    HAS_PAHO = False


# ═══════════════════════════════════════════════════════════════
#  ABSTRACT BRIDGE
# ═══════════════════════════════════════════════════════════════

class SensorBridge(ABC):
    """센서 데이터 수집을 위한 추상 인터페이스.

    모든 브릿지는 이 인터페이스를 구현한다.
    engine.py는 구체적 구현이 아닌 이 인터페이스에 의존한다.
    """

    @abstractmethod
    def connect(self) -> bool:
        """연결을 수립한다."""

    @abstractmethod
    def disconnect(self):
        """연결을 해제한다."""

    @abstractmethod
    def poll(self) -> list[dict]:
        """현재 센서 읽기값을 가져온다.

        Returns:
            list of dicts, 각 dict는 SensorSimulator.generate_readings()와 동일한 형식:
            {sensor_id, step_id, equip_id, sensor_type, value, unit,
             normal_min, normal_max, is_anomaly, timestamp}
        """

    @abstractmethod
    def publish_recovery(self, action: dict) -> bool:
        """복구 명령을 장비로 전송한다."""

    @abstractmethod
    def get_status(self) -> dict:
        """브릿지 상태를 반환한다."""


# ═══════════════════════════════════════════════════════════════
#  SIMULATED BRIDGE — 기존 SensorSimulator 래핑
# ═══════════════════════════════════════════════════════════════

class SimulatedBridge(SensorBridge):
    """기존 SensorSimulator를 SensorBridge 인터페이스로 래핑한다."""

    def __init__(self, sensor_sim):
        self.sensor_sim = sensor_sim
        self._connected = False

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self):
        self._connected = False

    def poll(self) -> list[dict]:
        if not self._connected:
            return []
        return self.sensor_sim.generate_readings()

    def publish_recovery(self, action: dict) -> bool:
        # 시뮬레이션에서는 복구가 DB 직접 조작으로 이루어짐
        return True

    def get_status(self) -> dict:
        return {
            "type": "simulated",
            "connected": self._connected,
            "sensor_count": len(self.sensor_sim.sensors) if self.sensor_sim else 0,
        }


# ═══════════════════════════════════════════════════════════════
#  MQTT BRIDGE — 실제 MQTT 브로커 연동
# ═══════════════════════════════════════════════════════════════

# Sparkplug B 호환 토픽 구조 (업계 표준)
# spBv1.0/{group_id}/DDATA/{edge_node_id}/{device_id}
TOPIC_SENSOR_DATA = "factory/+/sensor/+"       # factory/{area}/sensor/{step}
TOPIC_ALARM = "factory/+/alarm/+"              # factory/{area}/alarm/{step}
TOPIC_RECOVERY_CMD = "factory/recovery/cmd"    # 복구 명령 발행


class MQTTBridge(SensorBridge):
    """MQTT 브로커를 통한 실시간 센서 데이터 수집.

    업계 참조:
      - Sparkplug B: MQTT 기반 산업용 IoT 표준 (Eclipse Foundation)
      - AWS IoT Greengrass: 에지 → MQTT → 클라우드

    토픽 구조:
      factory/{area_id}/sensor/{step_id} → JSON payload
      factory/{area_id}/alarm/{step_id} → JSON payload
      factory/recovery/cmd → 복구 명령

    Payload 형식 (JSON):
      {"sensor_id": "SEN-0001", "sensor_type": "temperature",
       "value": 35.2, "unit": "°C", "timestamp": "2026-03-29T..."}
    """

    def __init__(self, broker: str = "localhost", port: int = 1883,
                 client_id: str = "ev-battery-aiops",
                 username: str | None = None, password: str | None = None):
        self.broker = broker
        self.port = port
        self.client_id = client_id
        self.username = username
        self.password = password
        self._client = None
        self._connected = False
        self._buffer = []  # 수신된 메시지 버퍼
        self._sensor_meta = {}  # sensor_id → {normal_min, normal_max, ...}

    def connect(self) -> bool:
        if not HAS_PAHO:
            raise ImportError(
                "paho-mqtt가 필요합니다: pip install paho-mqtt"
            )

        self._client = mqtt.Client(
            client_id=self.client_id,
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )
        if self.username:
            self._client.username_pw_set(self.username, self.password)

        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message

        try:
            self._client.connect(self.broker, self.port, keepalive=60)
            self._client.loop_start()
            # 연결 대기 (최대 5초)
            for _ in range(50):
                if self._connected:
                    return True
                time.sleep(0.1)
            return self._connected
        except Exception:
            return False

    def disconnect(self):
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
        self._connected = False

    def poll(self) -> list[dict]:
        """버퍼에 쌓인 메시지를 반환하고 비운다."""
        readings = list(self._buffer)
        self._buffer.clear()
        return readings

    def publish_recovery(self, action: dict) -> bool:
        """복구 명령을 MQTT로 발행한다."""
        if not self._connected or not self._client:
            return False
        try:
            payload = json.dumps(action, ensure_ascii=False)
            result = self._client.publish(TOPIC_RECOVERY_CMD, payload, qos=1)
            return result.rc == mqtt.MQTT_ERR_SUCCESS
        except Exception:
            return False

    def register_sensor_meta(self, sensor_id: str, meta: dict):
        """센서 메타데이터(정상 범위 등)를 등록한다."""
        self._sensor_meta[sensor_id] = meta

    def get_status(self) -> dict:
        return {
            "type": "mqtt",
            "connected": self._connected,
            "broker": f"{self.broker}:{self.port}",
            "buffer_size": len(self._buffer),
            "registered_sensors": len(self._sensor_meta),
        }

    # ── MQTT 콜백 ──

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            self._connected = True
            client.subscribe(TOPIC_SENSOR_DATA, qos=1)
            client.subscribe(TOPIC_ALARM, qos=1)
        else:
            self._connected = False

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            # 토픽에서 영역/스텝 정보 추출
            parts = msg.topic.split("/")
            # factory/{area}/sensor/{step} 형식
            if len(parts) >= 4 and parts[2] == "sensor":
                reading = self._normalize_reading(payload, parts)
                if reading:
                    self._buffer.append(reading)
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

    def _normalize_reading(self, payload: dict, topic_parts: list) -> dict | None:
        """MQTT 메시지를 SensorSimulator 호환 형식으로 변환한다."""
        sensor_id = payload.get("sensor_id", "")
        meta = self._sensor_meta.get(sensor_id, {})

        return {
            "sensor_id": sensor_id,
            "step_id": payload.get("step_id", topic_parts[3] if len(topic_parts) > 3 else "unknown"),
            "equip_id": payload.get("equip_id", meta.get("equip_id", "unknown")),
            "sensor_type": payload.get("sensor_type", "unknown"),
            "value": float(payload.get("value", 0)),
            "unit": payload.get("unit", ""),
            "normal_min": meta.get("normal_min"),
            "normal_max": meta.get("normal_max"),
            "is_anomaly": payload.get("is_anomaly", False),
            "timestamp": payload.get("timestamp", datetime.now(timezone.utc).isoformat()),
        }


# ═══════════════════════════════════════════════════════════════
#  OPC-UA BRIDGE — 인터페이스 (향후 구현)
# ═══════════════════════════════════════════════════════════════

class OPCUABridge(SensorBridge):
    """OPC-UA 서버 연동 인터페이스.

    업계 참조:
      - Siemens S7: OPC-UA 기본 탑재
      - Beckhoff TwinCAT: OPC-UA 서버 내장
      - Rockwell FactoryTalk: OPC-UA 게이트웨이

    구현 시 asyncua 라이브러리 사용 예정:
      pip install asyncua

    현재는 인터페이스만 정의하고, 실제 OPC-UA 연동은 Phase 2에서 구현한다.
    """

    def __init__(
        self,
        endpoint: str = "opc.tcp://localhost:4840",
        node_ids: dict[str, str] | None = None,
        username: str | None = None,
        password: str | None = None,
    ):
        """
        Parameters
        ----------
        endpoint : str
            OPC-UA 서버 endpoint (예: 'opc.tcp://192.168.1.10:4840').
        node_ids : dict[step_id, OPC-UA NodeId 문자열]
            ProcessStep을 OPC-UA 노드로 매핑. 미지정 시 빈 dict.
        username / password : OPC-UA 인증 (Basic256Sha256 등 정책 사용 시).
        """
        self.endpoint = endpoint
        self.node_ids: dict[str, str] = node_ids or {}
        self.username = username
        self.password = password
        self._connected = False
        self._client = None  # asyncua.Client 인스턴스 (런타임에 생성)
        self._asyncua_available = self._check_asyncua()

    @staticmethod
    def _check_asyncua() -> bool:
        try:
            import asyncua  # noqa: F401
            return True
        except Exception:
            return False

    def connect(self) -> bool:
        """OPC-UA 서버에 연결. asyncua 미설치 또는 연결 실패 시 False.

        실 연동은 sync wrapper로 asyncio.run을 호출하나, 메인 엔진의 이벤트
        루프와 충돌하지 않도록 별도 스레드/loop 사용 권장.
        """
        if not self._asyncua_available:
            return False
        try:
            from asyncua.sync import Client  # type: ignore[import-not-found]
            self._client = Client(url=self.endpoint)
            if self.username:
                self._client.set_user(self.username)
            if self.password:
                self._client.set_password(self.password)
            self._client.connect()
            self._connected = True
            return True
        except Exception:
            self._connected = False
            self._client = None
            return False

    def disconnect(self) -> None:
        try:
            if self._client is not None:
                self._client.disconnect()
        except Exception:
            pass
        finally:
            self._connected = False
            self._client = None

    def poll(self) -> list[dict]:
        """node_ids로 매핑된 step별 센서 값을 1회 읽기.

        반환 포맷: [{step_id, sensor, value, timestamp}, ...]
        """
        if not self._connected or self._client is None:
            return []
        readings = []
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).isoformat()
        for step_id, node_id_str in self.node_ids.items():
            try:
                node = self._client.get_node(node_id_str)
                value = node.read_value()
                readings.append({
                    "step_id": step_id,
                    "sensor": node_id_str,
                    "value": value,
                    "timestamp": ts,
                })
            except Exception:
                # 개별 노드 실패는 무시 (다음 폴링에서 재시도)
                continue
        return readings

    def publish_recovery(self, action: dict) -> bool:
        """RECOVER 액션을 OPC-UA write로 PLC에 반영 (예: setpoint 변경).

        action: {action_type, target_step, parameter, new_value}
        """
        if not self._connected or self._client is None:
            return False
        target_step = action.get("target_step")
        new_value = action.get("new_value")
        if not target_step or new_value is None:
            return False
        node_id_str = self.node_ids.get(target_step)
        if not node_id_str:
            return False
        try:
            node = self._client.get_node(node_id_str)
            node.write_value(new_value)
            return True
        except Exception:
            return False

    def get_status(self) -> dict:
        return {
            "type": "opcua",
            "connected": self._connected,
            "endpoint": self.endpoint,
            "asyncua_available": self._asyncua_available,
            "node_count": len(self.node_ids),
            "status": "ready" if self._connected else (
                "asyncua_missing" if not self._asyncua_available
                else "disconnected"
            ),
        }


# ═══════════════════════════════════════════════════════════════
#  FACTORY — 브릿지 생성
# ═══════════════════════════════════════════════════════════════

def create_bridge(protocol: str = "simulated", **kwargs) -> SensorBridge:
    """프로토콜 유형에 따라 적절한 브릿지를 생성한다.

    Args:
        protocol: "simulated", "mqtt", "opcua"
        **kwargs: 프로토콜별 설정
            - simulated: sensor_sim (SensorSimulator 인스턴스)
            - mqtt: broker, port, client_id, username, password
            - opcua: endpoint

    Returns:
        SensorBridge 인스턴스
    """
    if protocol == "mqtt":
        return MQTTBridge(
            broker=kwargs.get("broker", "localhost"),
            port=kwargs.get("port", 1883),
            client_id=kwargs.get("client_id", "ev-battery-aiops"),
            username=kwargs.get("username"),
            password=kwargs.get("password"),
        )
    elif protocol == "opcua":
        return OPCUABridge(
            endpoint=kwargs.get("endpoint", "opc.tcp://localhost:4840"),
        )
    else:
        return SimulatedBridge(
            sensor_sim=kwargs.get("sensor_sim"),
        )
