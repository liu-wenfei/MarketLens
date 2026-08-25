#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from marketlens.episode.freeze_record import validate_episode02_freeze_record


def main() -> int:
    result = validate_episode02_freeze_record(REPO_ROOT)
    payload = {
        "evidence_class": "NON-FORMAL / EPISODE 02 TRACKED FREEZE RECORD PREFLIGHT / ZERO-LLM",
        "llm_api_calls": 0,
        "formal_execution_performed_by_this_preflight": False,
        "formal_episode_mutated": False,
        **result,
    }
    print("NON-FORMAL / EPISODE 02 TRACKED FREEZE RECORD PREFLIGHT / ZERO-LLM")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
