#!/usr/bin/env python3
"""SGLang native /generate benchmark; model and verified budget are explicit."""

import sys

from perf_common import main as run_benchmark


def main(argv=None):
    return run_benchmark(argv, engine="sglang")


if __name__ == "__main__":
    sys.exit(main())
