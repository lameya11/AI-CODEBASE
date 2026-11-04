"""Timed step logger for the ingestion pipeline."""
import logging
import time
from contextlib import contextmanager
from typing import Generator

logger = logging.getLogger(__name__)


@contextmanager
def timed_step(name: str) -> Generator[None, None, None]:
    """Context manager that logs the duration of a named step in milliseconds."""
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info("[%s] completed in %.1f ms", name, elapsed_ms)
