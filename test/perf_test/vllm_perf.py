#!/usr/bin/env python3
"""vLLM benchmark entry point; see README.md for the shared evidence contract."""

import sys

from perf_common import main as run_benchmark


def main(argv=None):
    return run_benchmark(argv, engine="vllm")


if __name__ == "__main__":
    sys.exit(main())
