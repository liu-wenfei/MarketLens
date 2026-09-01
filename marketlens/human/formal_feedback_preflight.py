"""Guarded paid-provider preflight for formal feedback generation.

The default command is read-only and makes no provider request. Execution is
NON-FORMAL preflight evidence only and never reads or writes participant DBs.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Callable, Mapping

from marketlens.human.feedback import (
    CONTEXT_PACK_VERSION,
    FeedbackContextPack,
    FeedbackOutputValidationError,
    build_feedback_prompt,
    validate_feedback_output,
)
from marketlens.human.formal_feedback_generator import (
    FormalFeedbackGeneratorConfig,
    create_formal_openai_feedback_generator,
)


PREFLIGHT_CONTRACT_VERSION = (
    "marketlens-formal-feedback-provider-preflight-v1"
)
PREFLIGHT_LABEL = (
    "NON-FORMAL / PAID PROVIDER PREFLIGHT / "
    "NOT EXPERIMENTAL EVIDENCE"
)
PREFLIGHT_OUTPUT_RELATIVE = Path(
    "data/marketlens/human/preflight/"
    "formal_feedback_provider_v1"
)
EXECUTION_LOCK_NAME = "execution_lock.json"
SUCCESS_RECEIPT_NAME = "preflight_success.json"
FAILURE_RECEIPT_NAME = "preflight_failure.json"


class FormalFeedbackPreflightError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _sha256_json(value: object) -> str:
    return sha256(
        _canonical_json(value).encode("utf-8")
    ).hexdigest()


def build_preflight_context() -> FeedbackContextPack:
    """Build synthetic, non-participant FINAL context for compatibility."""

    window = {
        "start_period": 1,
        "end_period": 15,
        "periods_reviewed": 15,
    }

    return FeedbackContextPack(
        context_pack_version=CONTEXT_PACK_VERSION,
        context_policy_version=(
            "marketlens-formal-provider-preflight-context-v1"
        ),
        feedback_kind="final_session_summary",
        window=window,
        statistics={
            "window": window,
            "market_metrics": {
                "price_start": 10.0,
                "price_end": 12.0,
            },
            "confidence_metrics": {
                "first": 70.0,
                "latest": 60.0,
            },
            "trading_metrics": {
                "trade_periods": 5,
                "no_trade_periods": 10,
            },
            "portfolio_metrics": {
                "starting_value": 1000.0,
                "ending_value": 1010.0,
            },
        },
        information_environment={
            "available_news": [
                {
                    "period_number": 1,
                    "date": "2023-06-19",
                    "text": (
                        "A synthetic market update was available "
                        "during this provider compatibility check."
                    ),
                    "text_truncated": False,
                }
            ],
            "available_community_content": [],
            "released_controlled_information": [],
        },
        participant_reflections=(
            {
                "period_number": 1,
                "date": "2023-06-19",
                "within_period_sequence": 1,
                "action": "HOLD",
                "confidence": 70.0,
                "evidence_sources_selected": [],
                "evidence_sources_omitted": 0,
                "rationale": (
                    "This is synthetic preflight text and does not "
                    "represent a participant response."
                ),
                "rationale_truncated": False,
            },
        ),
        prior_context=None,
        context_coverage={
            "news_items_total": 1,
            "news_items_included": 1,
            "news_items_omitted": 0,
        },
    )


def _repo_state(repo_root: Path) -> dict[str, str]:
    def output(*args: str) -> str:
        return subprocess.check_output(
            ["git", *args],
            cwd=repo_root,
            text=True,
        ).strip()

    return {
        "branch": output("branch", "--show-current"),
        "commit": output("rev-parse", "HEAD"),
    }


def _require_clean_tracked_state(repo_root: Path) -> None:
    checks = (
        ("git working tree", ["git", "diff", "--quiet"]),
        (
            "git index",
            ["git", "diff", "--cached", "--quiet"],
        ),
    )
    for label, command in checks:
        completed = subprocess.run(
            command,
            cwd=repo_root,
            check=False,
        )
        if completed.returncode != 0:
            raise FormalFeedbackPreflightError(
                f"paid preflight requires a clean tracked {label}"
            )


def _write_exclusive(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as handle:
            json.dump(
                dict(payload),
                handle,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
                allow_nan=False,
            )
            handle.write("\n")
    except FileExistsError as exc:
        raise FormalFeedbackPreflightError(
            f"preflight file already exists: {path}"
        ) from exc


def _dry_run_report(
    *,
    prompt: object,
    config: FormalFeedbackGeneratorConfig,
) -> dict[str, object]:
    prompt_payload = prompt.to_dict()
    return {
        "status": "DRY_RUN_READY",
        "label": PREFLIGHT_LABEL,
        "preflight_contract_version": (
            PREFLIGHT_CONTRACT_VERSION
        ),
        "provider_request_made": False,
        "api_key_read": False,
        "maximum_provider_requests_if_executed": (
            config.max_provider_attempts
        ),
        "feedback_kind": prompt.feedback_kind,
        "prompt_contract_version": (
            prompt.prompt_contract_version
        ),
        "context_sha256": prompt.context_sha256,
        "prompt_sha256": _sha256_json(prompt_payload),
        "generator": config.static_metadata(),
        "execute_requirements": [
            "--execute",
            "--acknowledge-paid-api-call",
            "clean tracked git state",
            "OPENAI_API_KEY",
            "OPENAI_BASE_URL unset",
            "no previous execution lock",
        ],
    }


def run_preflight(
    *,
    execute: bool,
    acknowledge_paid_api_call: bool,
    repo_root: Path,
    output_root: Path,
    environ: Mapping[str, str] | None = None,
    client_factory: Callable[..., object] | None = None,
    enforce_clean_tracked_state: bool = True,
) -> dict[str, object]:
    config = FormalFeedbackGeneratorConfig()
    config.validate()
    context = build_preflight_context()
    prompt = build_feedback_prompt(context)

    if not execute:
        return _dry_run_report(
            prompt=prompt,
            config=config,
        )

    if not acknowledge_paid_api_call:
        raise FormalFeedbackPreflightError(
            "--execute requires --acknowledge-paid-api-call"
        )

    if enforce_clean_tracked_state:
        _require_clean_tracked_state(repo_root)

    source = os.environ if environ is None else environ
    if str(source.get("OPENAI_BASE_URL", "")).strip():
        raise FormalFeedbackPreflightError(
            "OPENAI_BASE_URL is prohibited in formal preflight"
        )
    if not str(source.get("OPENAI_API_KEY", "")).strip():
        raise FormalFeedbackPreflightError(
            "OPENAI_API_KEY is required for paid preflight"
        )

    state = _repo_state(repo_root)
    lock_path = output_root / EXECUTION_LOCK_NAME
    success_path = output_root / SUCCESS_RECEIPT_NAME
    failure_path = output_root / FAILURE_RECEIPT_NAME

    if lock_path.exists():
        raise FormalFeedbackPreflightError(
            "paid preflight already attempted; execution lock exists"
        )

    prompt_payload = prompt.to_dict()
    lock = {
        "status": "LOCKED_BEFORE_PROVIDER_REQUEST",
        "label": PREFLIGHT_LABEL,
        "preflight_contract_version": (
            PREFLIGHT_CONTRACT_VERSION
        ),
        "locked_at": _utc_now(),
        "git_branch": state["branch"],
        "git_commit": state["commit"],
        "prompt_contract_version": (
            prompt.prompt_contract_version
        ),
        "context_sha256": prompt.context_sha256,
        "prompt_sha256": _sha256_json(prompt_payload),
        "maximum_provider_requests": (
            config.max_provider_attempts
        ),
        "generator": config.static_metadata(),
    }
    _write_exclusive(lock_path, lock)

    try:
        generator = create_formal_openai_feedback_generator(
            environ=source,
            client_factory=client_factory,
            config=config,
        )
        result, validated = generator.generate_validated(
            prompt,
            validator=lambda output: validate_feedback_output(
                output,
                context_pack=context,
            ),
            validation_error_types=(
                FeedbackOutputValidationError,
            ),
        )
    except BaseException as exc:
        failure = {
            "status": "FAILED_CLOSED",
            "label": PREFLIGHT_LABEL,
            "preflight_contract_version": (
                PREFLIGHT_CONTRACT_VERSION
            ),
            "failed_at": _utc_now(),
            "git_branch": state["branch"],
            "git_commit": state["commit"],
            "prompt_sha256": lock["prompt_sha256"],
            "context_sha256": prompt.context_sha256,
            "error_type": type(exc).__name__,
            "fallback_used": False,
            "participant_db_touched": False,
        }
        _write_exclusive(failure_path, failure)
        raise

    validated_payload = dict(validated.payload)
    receipt = {
        "status": "PREFLIGHT_VALIDATED",
        "label": PREFLIGHT_LABEL,
        "preflight_contract_version": (
            PREFLIGHT_CONTRACT_VERSION
        ),
        "completed_at": _utc_now(),
        "git_branch": state["branch"],
        "git_commit": state["commit"],
        "prompt": prompt_payload,
        "prompt_sha256": lock["prompt_sha256"],
        "context_sha256": prompt.context_sha256,
        "generation_metadata": dict(result.metadata),
        "raw_output": result.output,
        "validated_output": validated_payload,
        "output_contract_version": (
            validated.output_contract_version
        ),
        "output_sha256": validated.output_sha256,
        "word_count": validated.word_count,
        "fallback_used": False,
        "participant_db_touched": False,
        "formal_experimental_evidence": False,
    }
    receipt["receipt_sha256"] = _sha256_json(receipt)
    _write_exclusive(success_path, receipt)
    return receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=PREFLIGHT_LABEL,
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="perform the bounded paid provider preflight",
    )
    parser.add_argument(
        "--acknowledge-paid-api-call",
        action="store_true",
        help="explicitly acknowledge that execute may incur API cost",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    repo_root = Path(__file__).resolve().parents[2]
    output_root = repo_root / PREFLIGHT_OUTPUT_RELATIVE

    try:
        report = run_preflight(
            execute=args.execute,
            acknowledge_paid_api_call=(
                args.acknowledge_paid_api_call
            ),
            repo_root=repo_root,
            output_root=output_root,
        )
    except BaseException as exc:
        print(
            f"FAIL CLOSED: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1

    print(
        json.dumps(
            report,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
