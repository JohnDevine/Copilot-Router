"""
@file benchmark.py
@brief Simple benchmarking module for logging model latency and performance.
"""

import time
from typing import Dict, Any, List

LOG: List[Dict[str, Any]] = []


def log_benchmark(model: str, prompt: str, start: float, end: float) -> None:
    """
    Logs the latency and metadata of a model execution.

    @param model Name of the model executed
    @param prompt The input prompt text (truncated to first 100 characters)
    @param start Timestamp when execution started
    @param end Timestamp when execution ended
    """
    latency: float = round(end - start, 3)
    LOG.append({
        "model": model,
        "prompt": prompt[:100],
        "latency": latency,
        "timestamp": time.time()
    })