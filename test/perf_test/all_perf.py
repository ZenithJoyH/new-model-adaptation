#!/usr/bin/env python3
"""Legacy vLLM multi-case entry point using the shared fail-closed runner. --input-len/--output-len/--concurrency remain supported with explicit model/tokenizer/context budget; --dry-run never produces acceptance evidence."""

import sys

from perf_common import main as run_benchmark


def main(argv=None):
    return run_benchmark(argv, engine="vllm", all_entrypoint=True)


if __name__ == "__main__":
    sys.exit(main())
