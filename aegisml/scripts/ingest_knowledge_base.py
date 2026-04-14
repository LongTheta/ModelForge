#!/usr/bin/env python3
"""
Load knowledge_base JSON documents into the Chroma collection (optional dependency).

Usage (from aegisml/):
  pip install -e ".[retrieval]"
  python scripts/ingest_knowledge_base.py
  python scripts/ingest_knowledge_base.py knowledge_base/samples
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

AEGISML_ROOT = Path(__file__).resolve().parents[1]
_SRC = AEGISML_ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def main() -> int:
    p = argparse.ArgumentParser(description="Ingest AegisML knowledge_base JSON into Chroma.")
    p.add_argument(
        "directory",
        nargs="?",
        default=str(AEGISML_ROOT / "knowledge_base" / "samples"),
        help="Directory of KB *.json files (default: knowledge_base/samples)",
    )
    p.add_argument(
        "--collection",
        default=None,
        help="Chroma collection name (default: env or aegisml_policy_kb)",
    )
    args = p.parse_args()
    root = Path(args.directory)
    if not root.is_dir():
        print(f"Not a directory: {root}", file=sys.stderr)
        return 1

    from retrieval.ingest_kb import ingest_kb_directory

    n = ingest_kb_directory(root, glob="**/*.json", collection_name=args.collection)
    print(f"Ingested {n} knowledge base file(s) from {root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
