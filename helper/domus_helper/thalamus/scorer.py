"""Shadow scorer slot. A scorer annotates a fire. It never decides."""
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Protocol


class Scorer(Protocol):
    def score(self, observation: dict) -> dict | None:
        ...


class NullScorer:
    def score(self, observation):
        return None


def load_scorer():
    name = os.environ.get("DOMUS_SHADOW_SCORER")
    if not name:
        return NullScorer(), None
    return NullScorer(), "unknown scorer %s" % name


def run_scorer(scorer, observation, timeout_s=2.0):
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        future = pool.submit(scorer.score, observation)
        try:
            result = future.result(timeout=timeout_s)
        except FuturesTimeout:
            return {"error": "timeout"}
        except Exception as exc:
            return {"error": "%s: %s" % (type(exc).__name__, exc)}
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    if result is None:
        return None
    if not isinstance(result, dict):
        return {"error": "scorer returned %s" % type(result).__name__}
    return result
