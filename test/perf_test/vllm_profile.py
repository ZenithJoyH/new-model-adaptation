#!/usr/bin/env python3
"""vLLM profiling entry point. Server profiler must already be configured; --profile-dir must expose its traces locally. Profiling and ordinary timing averages are kept separate."""

import sys

from perf_common import main as run_benchmark


def main(argv=None):
    return run_benchmark(argv, engine="vllm", profile=True)


if __name__ == "__main__":
    sys.exit(main())
