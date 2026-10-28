#!/usr/bin/env python3
"""Compare immutable-workload reports without mixing different benchmark versions."""
import argparse
import json
from pathlib import Path
import statistics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reports', nargs='+', help='benchmark-result.json paths')
    args = parser.parse_args()
    reports = [(Path(p), json.loads(Path(p).read_text())) for p in args.reports]
    hashes = {r['bundle_sha256'] for _, r in reports}
    if len(hashes) != 1:
        raise SystemExit('Cannot compare different bundle hashes')
    print('| Platform | Scenario | Pages/min median [min,max] | Page P90 seconds by round | SLO fraction | Fail/truncate |')
    print('|---|---|---:|---|---|---|')
    for path, report in reports:
        identity = json.loads((path.parent / 'run.json').read_text())
        for name in sorted({r['scenario'] for r in report['rounds']}):
            rounds = [r for r in report['rounds'] if r['scenario'] == name]
            speed = [r['successful_pages_per_minute'] for r in rounds]
            p90 = ', '.join(f"{r['page_latency_p90_seconds']:.2f}" for r in rounds)
            slo = ', '.join(f"{r['slo_success_fraction']:.1%}" for r in rounds)
            print(f"| {identity['label']} | {name} | {statistics.median(speed):.2f} [{min(speed):.2f},{max(speed):.2f}] | "
                  f"{p90} | {slo} | {sum(r['failed_requests'] for r in rounds)}/{sum(r['truncated_requests'] for r in rounds)} |")
        print(f"\nQuality: {report['quality_status']}; integrity: {report['all_integrity_ok']}; "
              f"stability: {report.get('steady_state_stable', 'not recorded')}\n")


if __name__ == '__main__':
    main()
