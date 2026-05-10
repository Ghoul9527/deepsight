import time


def now_ns() -> int:
    return time.monotonic_ns()


def now_ms() -> float:
    return time.monotonic() * 1000.0


def ns_to_seconds(ns: int) -> float:
    return ns / 1e9
