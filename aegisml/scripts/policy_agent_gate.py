#!/usr/bin/env python3
"""
Exit non-zero when ai-devsecops review-result.json should fail the pipeline.

Governance only — does not change runtime application behavior.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _fail_severities() -> set[str]:
    raw = os.environ.get("POLICY_CHECK_FAIL_SEVERITIES", "high,critical")
    return {x.strip().lower() for x in raw.split(",") if x.strip()}


def main() -> int:
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
    else:
        base = Path(os.environ.get("CI_PROJECT_DIR", "."))
        path = base / "artifacts" / "policy-check" / "review-result.json"

    if not path.is_file():
        print(f"ERROR: missing {path}", file=sys.stderr)
        return 1

    data = json.loads(path.read_text(encoding="utf-8"))
    verdict = data.get("verdict", "")
    findings = data.get("findings") or []
    fail_on = _fail_severities()
    bad = [f for f in findings if str(f.get("severity", "")).lower() in fail_on]

    print(f"verdict={verdict!r} findings_fail_severity={len(bad)}")
    for f in bad[:50]:
        title = f.get("title") or f.get("id") or "?"
        print(f"  - [{f.get('severity')}] {title}")

    if verdict == "fail" or bad:
        print(
            "policy_check: FAIL (verdict=fail and/or findings in "
            f"{sorted(fail_on)})",
            file=sys.stderr,
        )
        return 1
    print("policy_check: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
