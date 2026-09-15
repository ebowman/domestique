#!/usr/bin/env python3
"""Opt-in ONE index-only before/after fixture; 120s/operation, 300s overall.

Reuse identical topology, isolation and supervision from the path benchmark.
No native clients, DB, network or full matrices. Core starts at scope/core.
"""
import importlib.util
from pathlib import Path

from local_index_baseline import baseline

spec = importlib.util.spec_from_file_location(
    "path_benchmark", Path(__file__).with_name("global-path-benchmark.py"))
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


if __name__ == "__main__":
    fixture.main(restore=baseline, prefix="dom-index-timing-")
