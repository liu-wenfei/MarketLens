#!/usr/bin/env python3
"""Zero-LLM preflight for the tracked canonical episode-pool freeze record."""
from __future__ import annotations

import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from marketlens.episode.pool_freeze_record import validate_pool_freeze_record  # noqa: E402


def main() -> int:
    result = validate_pool_freeze_record(REPO_ROOT)
    payload = {
        "evidence_class": "NON-FORMAL / CANONICAL EPISODE POOL TRACKED FREEZE RECORD PREFLIGHT / ZERO-LLM",
        "llm_api_calls": 0,
        "formal_execution_performed_by_this_preflight": False,
        "formal_pool_mutated": False,
        **result,
    }
    print(payload["evidence_class"])
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
