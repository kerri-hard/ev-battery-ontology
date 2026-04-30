"""
Causal Discovery Engine — 자동 인과관계 발견
=============================================
기존 시딩된 CausalRule(15개)에 의존하는 대신,
센서 시계열 데이터에서 자동으로 새���운 인과관계를 발견한다.

학술 근거:
  - CausalTrace: Neurosymbolic Causal Analysis (arXiv, 2025)
  - Causal AI for Manufacturing RCA (Databricks, 2025)
  - Granger Causality (Econometrica, 1969) — 시계열 인과 검정의 기본

핵심 알고리즘:
  1. Granger Causality F-test: X가 Y를 예측하는 데 유의한 정보를 추가하는지 검정
  2. 조건부 독립성 가지치기: X→Y가 Z를 조건으로 했을 때 사라지면 가짜 인과
  3. Auto-Promotion: 발견된 인과관계 → CausalRule 노드로 온톨로지에 등록

개선 효과:
  - 도메인 전문가의 수동 시딩 의존성 탈피
  - 미지의 장애 패턴에 대한 자율 대응 능력 확보
  - 데이터 기반 인과관계 발견 → 설명 가능한 진단 강화
"""
import json
import math
import os
import random
from collections import defaultdict
from datetime import datetime

try:
    from scipy.stats import f as f_dist
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


class CausalDiscoveryEngine:
    """시계열 데이터에서 인과관계를 자동 발견한다.

    - Granger causality F-test로 시간적 선행/후행 인과 검정
    - 조건부 독립성 가지치기로 가짜 인과 제거
    - 발견된 관계를 CausalRule 노드로 자동 승격
    """

    def __init__(self, max_lag=2, significance=0.10, min_samples=10,
                 initial_strength_range=(0.4, 0.6)):
        self.max_lag = max_lag
        self.significance = significance
        self.min_samples = min_samples
        self.initial_strength_range = initial_strength_range
        self._discovery_counter = 0
        self.discovered_pairs: dict[tuple, dict] = {}  # (src_key, tgt_key) -> info
        self._promotion_log: list[dict] = []  # 승격 이력

    # ── MAIN ENTRY ────────────────────────────────────────

    def discover(self, correlation_analyzer) -> list[dict]:
        """상관관계가 높은 센서 쌍에 대해 Granger causality를 테스트한다.

        Args:
            correlation_analyzer: CorrelationAnalyzer 인스턴스 (series, known_correlations 사용)

        Returns:
            list of causal candidate dicts
        """
        if not HAS_SCIPY:
            return []

        candidates = []
        for (key_a, key_b), coeff in correlation_analyzer.known_correlations.items():
            if abs(coeff) < correlation_analyzer.threshold:
                continue

            series_a = correlation_analyzer.series.get(key_a, [])
            series_b = correlation_analyzer.series.get(key_b, [])
            n = min(len(series_a), len(series_b))
            if n < self.min_samples:
                continue

            x = series_a[-n:]
            y = series_b[-n:]

            # 양방향 검정: X→Y, Y→X
            result_xy = self.granger_test(x, y, self.max_lag)
            result_yx = self.granger_test(y, x, self.max_lag)

            step_a, sensor_a = key_a.split(":", 1)
            step_b, sensor_b = key_b.split(":", 1)

            # X→Y가 유의하고, Y→X보다 더 강하면 X가 Y를 야기
            if result_xy["significant"]:
                direction_strength = result_xy["f_stat"] - (result_yx["f_stat"] if result_yx["significant"] else 0)
                if direction_strength > 0:
                    candidates.append({
                        "source_step": step_a,
                        "source_sensor": sensor_a,
                        "target_step": step_b,
                        "target_sensor": sensor_b,
                        "f_stat": result_xy["f_stat"],
                        "p_value": result_xy["p_value"],
                        "best_lag": result_xy["best_lag"],
                        "correlation": coeff,
                        "direction_strength": direction_strength,
                        "cause_type": f"{sensor_a}_anomaly",
                        "effect_type": f"{sensor_b}_deviation",
                    })

            if result_yx["significant"]:
                direction_strength = result_yx["f_stat"] - (result_xy["f_stat"] if result_xy["significant"] else 0)
                if direction_strength > 0:
                    candidates.append({
                        "source_step": step_b,
                        "source_sensor": sensor_b,
                        "target_step": step_a,
                        "target_sensor": sensor_a,
                        "f_stat": result_yx["f_stat"],
                        "p_value": result_yx["p_value"],
                        "best_lag": result_yx["best_lag"],
                        "correlation": coeff,
                        "direction_strength": direction_strength,
                        "cause_type": f"{sensor_b}_anomaly",
                        "effect_type": f"{sensor_a}_deviation",
                    })

        # 방향 강도 높은 순으로 정렬
        candidates.sort(key=lambda c: -c["direction_strength"])
        return candidates

    def discover_with_context(
        self,
        correlation_analyzer,
        context_factor: str,
        bucket_masks: dict,
    ) -> dict:
        """Context-conditional Granger discovery — Bayesian 시작점.

        bucket_masks 의 각 bucket 별로 시계열을 마스킹해 Granger 별도 실행.
        결과: bucket 별 candidate 리스트 → 향후 ConditionalStrength 영속.

        Args:
            correlation_analyzer: CorrelationAnalyzer 인스턴스
            context_factor: 예 "time_of_day", "batch_id"
            bucket_masks: bucket_name → 시계열 인덱스별 boolean mask

        Returns:
            {bucket_name: [candidate_dict, ...]} — 각 bucket의 인과 후보.
            각 candidate에 context_factor / context_value / n_samples 포함.
        """
        if not HAS_SCIPY or not bucket_masks:
            return {}

        results: dict = {}
        for bucket_name, mask in bucket_masks.items():
            sub_candidates: list = []
            for (key_a, key_b), coeff in correlation_analyzer.known_correlations.items():
                series_a = correlation_analyzer.series.get(key_a, [])
                series_b = correlation_analyzer.series.get(key_b, [])
                n = min(len(series_a), len(series_b), len(mask))
                if n < self.min_samples:
                    continue
                x_sub = [series_a[i] for i in range(n) if mask[i]]
                y_sub = [series_b[i] for i in range(n) if mask[i]]
                if len(x_sub) < self.min_samples:
                    continue
                result_xy = self.granger_test(x_sub, y_sub, self.max_lag)
                if result_xy["significant"]:
                    step_a, sensor_a = key_a.split(":", 1)
                    step_b, sensor_b = key_b.split(":", 1)
                    sub_candidates.append({
                        "source_step": step_a, "source_sensor": sensor_a,
                        "target_step": step_b, "target_sensor": sensor_b,
                        "f_stat": result_xy["f_stat"],
                        "p_value": result_xy["p_value"],
                        "context_factor": context_factor,
                        "context_value": bucket_name,
                        "n_samples": len(x_sub),
                        "cause_type": f"{sensor_a}_anomaly",
                        "effect_type": f"{sensor_b}_deviation",
                    })
            sub_candidates.sort(key=lambda c: -c["f_stat"])
            results[bucket_name] = sub_candidates
        return results

    def granger_test(self, x: list, y: list, max_lag: int) -> dict:
        """X가 Y를 Granger-cause하는지 F-test로 검정한다.

        Restricted model:  y_t = Σ a_j * y_{t-j} + ε
        Unrestricted model: y_t = Σ a_j * y_{t-j} + Σ b_j * x_{t-j} + ε
        F = ((RSS_r - RSS_u) / p) / (RSS_u / (n - 2p - 1))
        """
        n = len(y)
        best_result = {"significant": False, "f_stat": 0.0, "p_value": 1.0, "best_lag": 0}

        for lag in range(1, min(max_lag + 1, n // 4)):
            if n - lag < 2 * lag + 2:
                continue

            # Build matrices
            Y = y[lag:]
            n_obs = len(Y)

            # Restricted: autoregression of y only
            X_r = []
            for t in range(n_obs):
                row = [y[t + lag - j - 1] for j in range(lag)]
                X_r.append(row)

            # Unrestricted: autoregression of y + lagged x
            X_u = []
            for t in range(n_obs):
                row_y = [y[t + lag - j - 1] for j in range(lag)]
                row_x = [x[t + lag - j - 1] for j in range(lag)]
                X_u.append(row_y + row_x)

            rss_r = self._ols_rss(X_r, Y)
            rss_u = self._ols_rss(X_u, Y)

            if rss_u <= 0 or rss_r <= 0:
                continue

            p = lag  # number of extra parameters
            dof1 = p
            dof2 = n_obs - 2 * lag - 1
            if dof2 <= 0:
                continue

            f_stat = ((rss_r - rss_u) / dof1) / (rss_u / dof2)
            if f_stat < 0:
                continue

            p_value = float(f_dist.sf(f_stat, dof1, dof2))

            if p_value < self.significance and f_stat > best_result["f_stat"]:
                best_result = {
                    "significant": True,
                    "f_stat": round(f_stat, 4),
                    "p_value": round(p_value, 6),
                    "best_lag": lag,
                }

        return best_result

    # ── CONDITIONAL INDEPENDENCE PRUNING ──────────────────

    def prune_conditional_independence(self, candidates: list[dict],
                                       correlation_analyzer) -> list[dict]:
        """조건부 독립성 검정으로 가짜 인과 엣지를 제거한다.

        X→Y에 대해, X와 Y 모두와 상관이 있는 Z가 존재할 때
        partial_corr(X,Y|Z)가 약해지면 X→Y는 가짜 인과로 제거.
        """
        if not candidates:
            return candidates

        pruned = []
        for cand in candidates:
            src_key = f"{cand['source_step']}:{cand['source_sensor']}"
            tgt_key = f"{cand['target_step']}:{cand['target_sensor']}"

            is_spurious = False

            # Z 후보: src, tgt 모두와 상관이 있는 제3의 센서
            for (ka, kb), coeff_z in correlation_analyzer.known_correlations.items():
                if abs(coeff_z) < correlation_analyzer.threshold:
                    continue

                # Z는 src 또는 tgt 중 하나와 상관이 있는 다른 키
                z_key = None
                if ka == src_key and kb != tgt_key:
                    z_key = kb
                elif kb == src_key and ka != tgt_key:
                    z_key = ka
                elif ka == tgt_key and kb != src_key:
                    z_key = kb
                elif kb == tgt_key and ka != src_key:
                    z_key = ka

                if z_key is None:
                    continue

                # Z가 두 쪽 모두와 상관이 있는지 확인
                r_xz = self._get_correlation(correlation_analyzer, src_key, z_key)
                r_yz = self._get_correlation(correlation_analyzer, tgt_key, z_key)
                r_xy = cand["correlation"]

                if abs(r_xz) < 0.3 or abs(r_yz) < 0.3:
                    continue

                # Partial correlation: r_XY|Z
                denom = math.sqrt(max(1e-10, (1 - r_xz ** 2) * (1 - r_yz ** 2)))
                partial_corr = (r_xy - r_xz * r_yz) / denom

                # 편상관이 크게 감소하면 가짜 인과
                if abs(partial_corr) < 0.25 and abs(r_xy) > 0.5:
                    is_spurious = True
                    break

            if not is_spurious:
                pruned.append(cand)

        return pruned

    # ── AUTO-PROMOTION TO ONTOLOGY ────────────────────────

    def promote_to_ontology(self, conn, candidates: list[dict],
                            counters: dict) -> list[dict]:
        """발견된 인과관계를 CausalRule 노드로 온톨로지에 등록한다.

        - ID: CR-DISC-XXXX (시드 규칙 CR-001~015, 자동규칙 CR-AUTO-*와 구분)
        - 초기 강도: 0.4~0.6 (시드 규칙 0.65~0.90보다 낮게)
        - confirmation_count = 0 (실제 복구 경험으로 강화 필요)
        """
        promoted = []

        for cand in candidates:
            pair_key = (
                f"{cand['source_step']}:{cand['source_sensor']}",
                f"{cand['target_step']}:{cand['target_sensor']}",
            )

            # 이미 발견된 쌍은 스킵
            if pair_key in self.discovered_pairs:
                continue

            # 이미 동일한 cause/effect 타입의 CausalRule이 있는지 확인
            cause_type = cand["cause_type"]
            effect_type = cand["effect_type"]
            try:
                r = conn.execute(
                    "MATCH (cr:CausalRule) WHERE cr.cause_type=$c AND cr.effect_type=$e "
                    "RETURN count(cr)",
                    {"c": cause_type, "e": effect_type},
                )
                if r.has_next() and int(r.get_next()[0]) > 0:
                    # 기존 규칙 존재 — strength만 확인하고 스킵
                    self.discovered_pairs[pair_key] = {"status": "already_exists"}
                    continue
            except Exception:
                pass

            self._discovery_counter += 1
            rule_id = f"CR-DISC-{self._discovery_counter:04d}"
            strength = round(
                random.uniform(*self.initial_strength_range), 3
            )
            name = (
                f"발견된 인과: {cand['source_step']}.{cand['source_sensor']} "
                f"→ {cand['target_step']}.{cand['target_sensor']} "
                f"(Granger p={cand['p_value']:.4f})"
            )

            now_iso = datetime.now().isoformat()
            try:
                conn.execute(
                    "CREATE (cr:CausalRule {"
                    "id: $id, name: $name, cause_type: $cause, effect_type: $effect, "
                    "strength: $str, confirmation_count: 0, last_confirmed: $ts})",
                    {
                        "id": rule_id,
                        "name": name,
                        "cause": cause_type,
                        "effect": effect_type,
                        "str": strength,
                        "ts": now_iso,
                    },
                )

                # source_step → CausalRule 연결 (HAS_CAUSE)
                try:
                    conn.execute(
                        "MATCH (ps:ProcessStep), (cr:CausalRule) "
                        "WHERE ps.id=$step AND cr.id=$cr "
                        "CREATE (ps)-[:HAS_CAUSE]->(cr)",
                        {"step": cand["source_step"], "cr": rule_id},
                    )
                except Exception:
                    pass

                # target_step → CausalRule 연결
                try:
                    conn.execute(
                        "MATCH (ps:ProcessStep), (cr:CausalRule) "
                        "WHERE ps.id=$step AND cr.id=$cr "
                        "CREATE (ps)-[:HAS_CAUSE]->(cr)",
                        {"step": cand["target_step"], "cr": rule_id},
                    )
                except Exception:
                    pass

                promoted_info = {
                    "id": rule_id,
                    "cause_type": cause_type,
                    "effect_type": effect_type,
                    "strength": strength,
                    "source_step": cand["source_step"],
                    "target_step": cand["target_step"],
                    "p_value": cand["p_value"],
                    "f_stat": cand["f_stat"],
                    "best_lag": cand["best_lag"],
                }
                promoted.append(promoted_info)
                self.discovered_pairs[pair_key] = promoted_info
                self._promotion_log.append({
                    **promoted_info,
                    "timestamp": now_iso,
                })

            except Exception:
                pass

        return promoted

    # ── STATUS ────────────���───────────────────────────────

    def get_status(self) -> dict:
        """인과 발견 엔진의 현재 상태를 반환한다."""
        return {
            "total_discovered": len(self.discovered_pairs),
            "total_promoted": len(self._promotion_log),
            "recent_promotions": self._promotion_log[-10:],
            "config": {
                "max_lag": self.max_lag,
                "significance": self.significance,
                "min_samples": self.min_samples,
                "initial_strength_range": list(self.initial_strength_range),
            },
            "scipy_available": HAS_SCIPY,
        }

    # ── INTERNAL HELPERS ──────────────────────────────────

    @staticmethod
    def _ols_rss(X: list[list[float]], Y: list[float]) -> float:
        """OLS (Ordinary Least Squares) 잔차 제곱합을 계산한다.

        정규 방정식 풀이: β = (X'X)^{-1} X'Y, RSS = Σ(y - Xβ)^2
        행렬 연산을 순수 Python으로 구현 (numpy 미사용).
        """
        n = len(Y)
        p = len(X[0]) if X else 0
        if n <= p or p == 0:
            return float("inf")

        # X'X (p x p)
        xtx = [[0.0] * p for _ in range(p)]
        for i in range(p):
            for j in range(p):
                s = 0.0
                for t in range(n):
                    s += X[t][i] * X[t][j]
                xtx[i][j] = s

        # X'Y (p x 1)
        xty = [0.0] * p
        for i in range(p):
            s = 0.0
            for t in range(n):
                s += X[t][i] * Y[t]
            xty[i] = s

        # Solve via Gauss elimination
        aug = [xtx[i][:] + [xty[i]] for i in range(p)]
        for col in range(p):
            # Pivot
            max_row = col
            for row in range(col + 1, p):
                if abs(aug[row][col]) > abs(aug[max_row][col]):
                    max_row = row
            aug[col], aug[max_row] = aug[max_row], aug[col]

            if abs(aug[col][col]) < 1e-12:
                return float("inf")

            for row in range(col + 1, p):
                factor = aug[row][col] / aug[col][col]
                for k in range(col, p + 1):
                    aug[row][k] -= factor * aug[col][k]

        # Back substitution
        beta = [0.0] * p
        for i in range(p - 1, -1, -1):
            s = aug[i][p]
            for j in range(i + 1, p):
                s -= aug[i][j] * beta[j]
            beta[i] = s / aug[i][i] if abs(aug[i][i]) > 1e-12 else 0.0

        # RSS = Σ(y_t - X_t @ β)^2
        rss = 0.0
        for t in range(n):
            pred = sum(X[t][j] * beta[j] for j in range(p))
            rss += (Y[t] - pred) ** 2

        return rss

    @staticmethod
    def _get_correlation(corr_analyzer, key_a: str, key_b: str) -> float:
        """CorrelationAnalyzer에서 두 키 간 상관계수를 조회한다."""
        c = corr_analyzer.known_correlations.get((key_a, key_b))
        if c is not None:
            return c
        c = corr_analyzer.known_correlations.get((key_b, key_a))
        if c is not None:
            return c
        return 0.0

    # ── PERSISTENCE (vision: "실패에서 성장하는 시스템") ───

    def save_state(self, path: str) -> bool:
        """발견된 인과 쌍과 승격 이력을 JSON으로 저장한다."""
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            # tuple 키는 JSON 직렬화 불가 → "src_key||tgt_key" 형식으로 변환
            serialized_pairs = {
                f"{k[0]}||{k[1]}": v for k, v in self.discovered_pairs.items()
            }
            payload = {
                "saved_at": datetime.now().isoformat(),
                "config": {
                    "max_lag": self.max_lag,
                    "significance": self.significance,
                    "min_samples": self.min_samples,
                },
                "discovery_counter": self._discovery_counter,
                "discovered_pairs": serialized_pairs,
                "promotion_log": self._promotion_log[-50:],
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    def load_state(self, path: str) -> bool:
        """이전 발견 상태를 복원한다."""
        if not os.path.exists(path):
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            self._discovery_counter = payload.get("discovery_counter", 0)
            self._promotion_log = payload.get("promotion_log", [])
            for key, v in payload.get("discovered_pairs", {}).items():
                parts = key.split("||", 1)
                if len(parts) == 2:
                    self.discovered_pairs[(parts[0], parts[1])] = v
            return True
        except Exception:
            return False
