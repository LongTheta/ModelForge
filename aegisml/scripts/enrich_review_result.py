#!/usr/bin/env python3
"""
Enrich GitLab policy-agent ``review-result.json`` findings with KB retrieval.

Does not change ``verdict`` or severities — only adds explanation fields per finding.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

AEGISML_ROOT = Path(__file__).resolve().parents[1]
_SRC = AEGISML_ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def main() -> int:
    p = argparse.ArgumentParser(description="Enrich policy review JSON with retrieval context.")
    p.add_argument(
        "path",
        type=Path,
        help="Path to review-result.json (overwritten unless --out is set)",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write enriched JSON here instead of overwriting the input",
    )
    args = p.parse_args()

    path: Path = args.path
    if not path.is_file():
        print(f"ERROR: not a file: {path}", file=sys.stderr)
        return 1

    data = json.loads(path.read_text(encoding="utf-8"))
    try:
        from retrieval.enrich import enrich_policy_payload

        out_doc = enrich_policy_payload(data)
    except ImportError:
        print("ERROR: retrieval package not importable", file=sys.stderr)
        return 1

    dest = args.out or path
    dest.write_text(json.dumps(out_doc, indent=2), encoding="utf-8")
    print(f"Wrote enriched findings to {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
