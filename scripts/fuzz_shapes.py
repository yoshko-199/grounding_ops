#!/usr/bin/env python3
"""Fuzz the engine over generated claim shapes.

    python3 scripts/fuzz_shapes.py                 # a bounded sample
    python3 scripts/fuzz_shapes.py --all           # every shape
    python3 scripts/fuzz_shapes.py --seed 7        # a different sample

Checks properties that must hold for every claim whatever the verdict —
whether the render survives, whether the ledger contradicts the routing note,
whether a period was compared as a figure. It has no ground truth and does not
try to judge whether a verdict is right.

Failures are shrunk before they are reported, so what comes back is the
shortest claim that still exhibits the defect.

Exit codes:
    0  no violations
    1  at least one violation or crash
"""

from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from plugins.shapes.run import fuzz  # noqa: E402
from plugins.shapes.shapes import generate  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fuzz the engine over claim shapes.")
    parser.add_argument("--count", type=int, default=500, metavar="N")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--all", action="store_true", help="check every shape")
    parser.add_argument("--packs", type=pathlib.Path, default=None)
    args = parser.parse_args(argv)

    count = len(generate()) if args.all else args.count
    report = fuzz(count=count, seed=args.seed, packs=args.packs)

    for violation in report.violations:
        print(violation)
        print()
    for claim, detail in report.crashed:
        print(f"[pipeline-crash] {claim!r}\n    {detail}\n")

    print(report.summary())
    if not report.clean:
        print(
            f"\nReproduce with: python3 scripts/fuzz_shapes.py "
            f"--count {count} --seed {args.seed}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
