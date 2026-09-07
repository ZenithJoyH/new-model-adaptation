#!/usr/bin/env python3
"""SGLang profiling entry point. Configure SGLANG_TORCH_PROFILER_DIR on the server before launch and expose that directory via --profile-dir. This client never restarts/configures the server."""

import sys

from perf_common import main as run_benchmark


def main(argv=None):
    return run_benchmark(argv, engine="sglang", profile=True)


if __name__ == "__main__":
    sys.exit(main())
