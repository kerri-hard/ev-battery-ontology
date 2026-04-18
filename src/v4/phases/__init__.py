"""SelfHealingEngine 자율 복구 루프 페이즈 모듈.

각 페이즈는 `async def run(engine, ...) -> dict` 시그니처를 가지며
이전 페이즈의 출력을 입력으로 받아 다음 페이즈로 데이터를 전달한다.

Phase order: SCENARIO → SENSE → DETECT → DIAGNOSE → RECOVER → VERIFY → LEARN → PERIODIC
"""

from v4.phases import sense, detect, diagnose, preverify, recover, verify, learn, periodic

__all__ = ["sense", "detect", "diagnose", "preverify", "recover", "verify", "learn", "periodic"]
