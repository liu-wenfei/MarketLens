"""Immutable candidate/review/accepted lifecycle for formal feedback.

This module is deliberately provider-neutral and uses only the Python standard
library. It never reads credentials, creates an API client, touches participant
databases, or promotes a candidate without one explicit immutable ACCEPT
review.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any
from uuid import uuid4


REVIEW_ARTIFACT_CONTRACT_VERSION = (
    "marketlens-formal-feedback-review-artifact-v1"
)
CANDIDATE_STATUS = "CANDIDATE"
REVIEW_STATUS = "REVIEWED"
ACCEPTED_STATUS = "ACCEPTED"
REVIEW_ACCEPT = "ACCEPT"
REVIEW_REJECT = "REJECT"

_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_PROMPT_FIELDS = frozenset(
    {
        "prompt_contract_version",
        "context_pack_version",
        "context_policy_version",
        "context_sha256",
        "feedback_kind",
        "system_prompt",
        "user_prompt",
    }
)
_VALIDATED_OUTPUT_FIELDS = frozenset(
    {"feedback_kind", "reflection"}
)
_CANDIDATE_FIELDS = frozenset(
    {
        "artifact_contract_version",
        "status",
        "prompt_sha256",
        "context_sha256",
        "feedback_kind",
        "context_pack",
        "prompt",
        "generator_id",
        "generation_metadata",
        "raw_output",
        "validated_output",
        "output_contract_version",
        "output_sha256",
        "word_count",
        "generated_at",
        "candidate_sha256",
    }
)
_REVIEW_FIELDS = frozenset(
    {
        "artifact_contract_version",
        "status",
        "prompt_sha256",
        "candidate_sha256",
        "decision",
        "reviewer_id",
        "review_notes",
        "reviewed_at",
        "review_sha256",
    }
)
_ACCEPTED_FIELDS = frozenset(
    {
        "artifact_contract_version",
        "status",
        "prompt_sha256",
        "context_sha256",
        "feedback_kind",
        "candidate_sha256",
        "review_sha256",
        "reviewer_id",
        "generator_id",
        "generation_metadata",
        "raw_output",
        "validated_output",
        "output_contract_version",
        "output_sha256",
        "word_count",
        "generated_at",
        "reviewed_at",
        "accepted_at",
        "accepted_sha256",
    }
)
_SECRET_METADATA_KEYS = frozenset(
    {
        "api_key",
        "openai_api_key",
        "authorization",
        "access_token",
        "secret",
    }
)


class FeedbackReviewArtifactError(ValueError):
    """Raised when an artifact is malformed or fails provenance checks."""


class FeedbackReviewArtifactConflictError(
    FeedbackReviewArtifactError
):
    """Raised when an immutable artifact path has different content."""


def _canonical_json(value: object) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise FeedbackReviewArtifactError(
            "feedback review artifact must be canonical JSON"
        ) from exc


def _detached(value: object) -> Any:
    return json.loads(_canonical_json(value))


def _sha256_json(value: object) -> str:
    return sha256(
        _canonical_json(value).encode("utf-8")
    ).hexdigest()


def _mapping(name: str, value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise FeedbackReviewArtifactError(
            f"{name} must be a mapping"
        )
    detached = _detached(dict(value))
    if not isinstance(detached, dict):
        raise FeedbackReviewArtifactError(
            f"{name} must be a JSON object"
        )
    return detached


def _exact_fields(
    name: str,
    value: Mapping[str, object],
    expected: frozenset[str],
) -> None:
    actual = set(value)
    if actual != set(expected):
        raise FeedbackReviewArtifactError(
            f"{name} fields are invalid: "
            f"missing={sorted(set(expected) - actual)}, "
            f"extra={sorted(actual - set(expected))}"
        )


def _nonempty_text(
    name: str,
    value: object,
    *,
    maximum: int | None = None,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FeedbackReviewArtifactError(
            f"{name} must be non-empty text"
        )
    result = value.strip()
    if maximum is not None and len(result) > maximum:
        raise FeedbackReviewArtifactError(
            f"{name} exceeds {maximum} characters"
        )
    return result


def _optional_text(
    name: str,
    value: object,
    *,
    maximum: int,
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise FeedbackReviewArtifactError(
            f"{name} must be text or null"
        )
    result = value.strip()
    if len(result) > maximum:
        raise FeedbackReviewArtifactError(
            f"{name} exceeds {maximum} characters"
        )
    return result or None


def _timestamp(name: str, value: object) -> str:
    text = _nonempty_text(name, value)
    try:
        parsed = datetime.fromisoformat(
            text.replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise FeedbackReviewArtifactError(
            f"{name} must be an ISO-8601 timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise FeedbackReviewArtifactError(
            f"{name} must include a UTC offset"
        )
    return parsed.isoformat()


def _hex_digest(name: str, value: object) -> str:
    if not isinstance(value, str) or not _HEX_64.fullmatch(value):
        raise FeedbackReviewArtifactError(
            f"{name} must be a lowercase SHA-256 digest"
        )
    return value


def _strict_positive_int(name: str, value: object) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value <= 0
    ):
        raise FeedbackReviewArtifactError(
            f"{name} must be a positive integer"
        )
    return value


def _hash_without(
    record: Mapping[str, object],
    hash_field: str,
) -> str:
    payload = dict(record)
    if hash_field not in payload:
        raise FeedbackReviewArtifactError(
            f"artifact is missing {hash_field}"
        )
    del payload[hash_field]
    return _sha256_json(payload)


def _reject_secret_metadata(
    value: object,
    *,
    location: str = "generation_metadata",
) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            if key_text.lower() in _SECRET_METADATA_KEYS:
                raise FeedbackReviewArtifactError(
                    f"secret field is forbidden at {location}.{key_text}"
                )
            _reject_secret_metadata(
                child,
                location=f"{location}.{key_text}",
            )
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _reject_secret_metadata(
                child,
                location=f"{location}[{index}]",
            )
        return
    if isinstance(value, str) and value.strip().startswith("sk-"):
        raise FeedbackReviewArtifactError(
            f"credential-shaped value is forbidden at {location}"
        )


def _validated_output(value: object) -> dict[str, object]:
    result = _mapping("validated_output", value)
    _exact_fields(
        "validated_output",
        result,
        _VALIDATED_OUTPUT_FIELDS,
    )
    _nonempty_text("validated_output.feedback_kind", result["feedback_kind"])
    _nonempty_text("validated_output.reflection", result["reflection"])
    return result


def _raw_output(value: object) -> str:
    if isinstance(value, Mapping):
        return _canonical_json(dict(value))
    return _nonempty_text("raw_output", value)


def _parsed_raw_output(value: object) -> dict[str, object]:
    text = _raw_output(value)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise FeedbackReviewArtifactError(
            "raw_output must contain one JSON object"
        ) from exc
    if not isinstance(parsed, dict):
        raise FeedbackReviewArtifactError(
            "raw_output JSON root must be an object"
        )
    return _detached(parsed)


def _prompt_payload(value: object) -> dict[str, object]:
    prompt = _mapping("prompt", value)
    _exact_fields("prompt", prompt, _PROMPT_FIELDS)
    for field in _PROMPT_FIELDS:
        _nonempty_text(f"prompt.{field}", prompt[field])
    _hex_digest("prompt.context_sha256", prompt["context_sha256"])
    return prompt


def build_candidate_record(
    *,
    context_pack: Mapping[str, object],
    prompt: Mapping[str, object],
    generator_id: str,
    generation_metadata: Mapping[str, object],
    raw_output: str | Mapping[str, object],
    validated_output: Mapping[str, object],
    output_contract_version: str,
    output_sha256: str,
    word_count: int,
    generated_at: str,
) -> dict[str, object]:
    """Build one immutable, already-deterministically-validated candidate."""

    detached_context = _mapping("context_pack", context_pack)
    detached_prompt = _prompt_payload(prompt)
    detached_output = _validated_output(validated_output)
    detached_metadata = _mapping(
        "generation_metadata",
        generation_metadata,
    )
    _reject_secret_metadata(detached_metadata)

    context_sha256 = _sha256_json(detached_context)
    if detached_prompt["context_sha256"] != context_sha256:
        raise FeedbackReviewArtifactError(
            "prompt context_sha256 does not match context_pack"
        )

    prompt_sha256 = _sha256_json(detached_prompt)
    feedback_kind = _nonempty_text(
        "prompt.feedback_kind",
        detached_prompt["feedback_kind"],
    )
    if detached_output["feedback_kind"] != feedback_kind:
        raise FeedbackReviewArtifactError(
            "validated feedback_kind does not match prompt"
        )

    canonical_output_sha256 = _sha256_json(detached_output)
    if _hex_digest("output_sha256", output_sha256) != canonical_output_sha256:
        raise FeedbackReviewArtifactError(
            "output_sha256 does not match validated_output"
        )

    canonical_raw = _raw_output(raw_output)
    if _parsed_raw_output(canonical_raw) != detached_output:
        raise FeedbackReviewArtifactError(
            "raw_output does not match validated_output"
        )

    record: dict[str, object] = {
        "artifact_contract_version": (
            REVIEW_ARTIFACT_CONTRACT_VERSION
        ),
        "status": CANDIDATE_STATUS,
        "prompt_sha256": prompt_sha256,
        "context_sha256": context_sha256,
        "feedback_kind": feedback_kind,
        "context_pack": detached_context,
        "prompt": detached_prompt,
        "generator_id": _nonempty_text(
            "generator_id",
            generator_id,
        ),
        "generation_metadata": detached_metadata,
        "raw_output": canonical_raw,
        "validated_output": detached_output,
        "output_contract_version": _nonempty_text(
            "output_contract_version",
            output_contract_version,
        ),
        "output_sha256": canonical_output_sha256,
        "word_count": _strict_positive_int(
            "word_count",
            word_count,
        ),
        "generated_at": _timestamp(
            "generated_at",
            generated_at,
        ),
    }
    record["candidate_sha256"] = _sha256_json(record)
    return verify_candidate_record(record)


def verify_candidate_record(
    value: Mapping[str, object],
) -> dict[str, object]:
    record = _mapping("candidate", value)
    _exact_fields("candidate", record, _CANDIDATE_FIELDS)
    if record["artifact_contract_version"] != (
        REVIEW_ARTIFACT_CONTRACT_VERSION
    ):
        raise FeedbackReviewArtifactError(
            "candidate artifact contract version mismatch"
        )
    if record["status"] != CANDIDATE_STATUS:
        raise FeedbackReviewArtifactError(
            "candidate status mismatch"
        )

    prompt = _prompt_payload(record["prompt"])
    context = _mapping("context_pack", record["context_pack"])
    context_hash = _sha256_json(context)
    prompt_hash = _sha256_json(prompt)
    if record["context_sha256"] != context_hash:
        raise FeedbackReviewArtifactError(
            "candidate context hash mismatch"
        )
    if prompt["context_sha256"] != context_hash:
        raise FeedbackReviewArtifactError(
            "candidate prompt/context binding mismatch"
        )
    if record["prompt_sha256"] != prompt_hash:
        raise FeedbackReviewArtifactError(
            "candidate prompt hash mismatch"
        )

    output = _validated_output(record["validated_output"])
    if record["feedback_kind"] != prompt["feedback_kind"]:
        raise FeedbackReviewArtifactError(
            "candidate feedback_kind/prompt mismatch"
        )
    if output["feedback_kind"] != record["feedback_kind"]:
        raise FeedbackReviewArtifactError(
            "candidate feedback_kind/output mismatch"
        )
    if _parsed_raw_output(record["raw_output"]) != output:
        raise FeedbackReviewArtifactError(
            "candidate raw/validated output mismatch"
        )
    if record["output_sha256"] != _sha256_json(output):
        raise FeedbackReviewArtifactError(
            "candidate output hash mismatch"
        )

    _hex_digest("prompt_sha256", record["prompt_sha256"])
    _hex_digest("context_sha256", record["context_sha256"])
    candidate_hash = _hex_digest(
        "candidate_sha256",
        record["candidate_sha256"],
    )
    if candidate_hash != _hash_without(
        record,
        "candidate_sha256",
    ):
        raise FeedbackReviewArtifactError(
            "candidate record hash mismatch"
        )

    _nonempty_text("generator_id", record["generator_id"])
    metadata = _mapping(
        "generation_metadata",
        record["generation_metadata"],
    )
    _reject_secret_metadata(metadata)
    _nonempty_text(
        "output_contract_version",
        record["output_contract_version"],
    )
    _strict_positive_int("word_count", record["word_count"])
    _timestamp("generated_at", record["generated_at"])
    return record


def build_review_record(
    *,
    candidate: Mapping[str, object],
    decision: str,
    reviewer_id: str,
    reviewed_at: str,
    review_notes: str | None = None,
) -> dict[str, object]:
    verified = verify_candidate_record(candidate)
    resolved_decision = _nonempty_text(
        "decision",
        decision,
    ).upper()
    if resolved_decision not in {REVIEW_ACCEPT, REVIEW_REJECT}:
        raise FeedbackReviewArtifactError(
            "review decision must be ACCEPT or REJECT"
        )

    record: dict[str, object] = {
        "artifact_contract_version": (
            REVIEW_ARTIFACT_CONTRACT_VERSION
        ),
        "status": REVIEW_STATUS,
        "prompt_sha256": verified["prompt_sha256"],
        "candidate_sha256": verified["candidate_sha256"],
        "decision": resolved_decision,
        "reviewer_id": _nonempty_text(
            "reviewer_id",
            reviewer_id,
            maximum=128,
        ),
        "review_notes": _optional_text(
            "review_notes",
            review_notes,
            maximum=2000,
        ),
        "reviewed_at": _timestamp(
            "reviewed_at",
            reviewed_at,
        ),
    }
    record["review_sha256"] = _sha256_json(record)
    return verify_review_record(
        record,
        candidate=verified,
    )


def verify_review_record(
    value: Mapping[str, object],
    *,
    candidate: Mapping[str, object] | None = None,
) -> dict[str, object]:
    record = _mapping("review", value)
    _exact_fields("review", record, _REVIEW_FIELDS)
    if record["artifact_contract_version"] != (
        REVIEW_ARTIFACT_CONTRACT_VERSION
    ):
        raise FeedbackReviewArtifactError(
            "review artifact contract version mismatch"
        )
    if record["status"] != REVIEW_STATUS:
        raise FeedbackReviewArtifactError(
            "review status mismatch"
        )
    if record["decision"] not in {REVIEW_ACCEPT, REVIEW_REJECT}:
        raise FeedbackReviewArtifactError(
            "review decision mismatch"
        )
    _hex_digest("prompt_sha256", record["prompt_sha256"])
    _hex_digest("candidate_sha256", record["candidate_sha256"])
    review_hash = _hex_digest(
        "review_sha256",
        record["review_sha256"],
    )
    if review_hash != _hash_without(record, "review_sha256"):
        raise FeedbackReviewArtifactError(
            "review record hash mismatch"
        )
    _nonempty_text(
        "reviewer_id",
        record["reviewer_id"],
        maximum=128,
    )
    _optional_text(
        "review_notes",
        record["review_notes"],
        maximum=2000,
    )
    _timestamp("reviewed_at", record["reviewed_at"])

    if candidate is not None:
        verified_candidate = verify_candidate_record(candidate)
        if record["prompt_sha256"] != verified_candidate["prompt_sha256"]:
            raise FeedbackReviewArtifactError(
                "review prompt does not match candidate"
            )
        if record["candidate_sha256"] != verified_candidate["candidate_sha256"]:
            raise FeedbackReviewArtifactError(
                "review candidate hash does not match"
            )
    return record


def build_accepted_record(
    *,
    candidate: Mapping[str, object],
    review: Mapping[str, object],
    accepted_at: str,
) -> dict[str, object]:
    verified_candidate = verify_candidate_record(candidate)
    verified_review = verify_review_record(
        review,
        candidate=verified_candidate,
    )
    if verified_review["decision"] != REVIEW_ACCEPT:
        raise FeedbackReviewArtifactError(
            "only an ACCEPT review can be promoted"
        )

    record: dict[str, object] = {
        "artifact_contract_version": (
            REVIEW_ARTIFACT_CONTRACT_VERSION
        ),
        "status": ACCEPTED_STATUS,
        "prompt_sha256": verified_candidate["prompt_sha256"],
        "context_sha256": verified_candidate["context_sha256"],
        "feedback_kind": verified_candidate["feedback_kind"],
        "candidate_sha256": verified_candidate["candidate_sha256"],
        "review_sha256": verified_review["review_sha256"],
        "reviewer_id": verified_review["reviewer_id"],
        "generator_id": verified_candidate["generator_id"],
        "generation_metadata": verified_candidate["generation_metadata"],
        "raw_output": verified_candidate["raw_output"],
        "validated_output": verified_candidate["validated_output"],
        "output_contract_version": verified_candidate[
            "output_contract_version"
        ],
        "output_sha256": verified_candidate["output_sha256"],
        "word_count": verified_candidate["word_count"],
        "generated_at": verified_candidate["generated_at"],
        "reviewed_at": verified_review["reviewed_at"],
        "accepted_at": _timestamp("accepted_at", accepted_at),
    }
    record["accepted_sha256"] = _sha256_json(record)
    return verify_accepted_record(
        record,
        candidate=verified_candidate,
        review=verified_review,
    )


def verify_accepted_record(
    value: Mapping[str, object],
    *,
    candidate: Mapping[str, object] | None = None,
    review: Mapping[str, object] | None = None,
) -> dict[str, object]:
    record = _mapping("accepted", value)
    _exact_fields("accepted", record, _ACCEPTED_FIELDS)
    if record["artifact_contract_version"] != (
        REVIEW_ARTIFACT_CONTRACT_VERSION
    ):
        raise FeedbackReviewArtifactError(
            "accepted artifact contract version mismatch"
        )
    if record["status"] != ACCEPTED_STATUS:
        raise FeedbackReviewArtifactError(
            "accepted status mismatch"
        )

    for field in (
        "prompt_sha256",
        "context_sha256",
        "candidate_sha256",
        "review_sha256",
        "output_sha256",
    ):
        _hex_digest(field, record[field])
    accepted_hash = _hex_digest(
        "accepted_sha256",
        record["accepted_sha256"],
    )
    if accepted_hash != _hash_without(record, "accepted_sha256"):
        raise FeedbackReviewArtifactError(
            "accepted record hash mismatch"
        )

    output = _validated_output(record["validated_output"])
    if _parsed_raw_output(record["raw_output"]) != output:
        raise FeedbackReviewArtifactError(
            "accepted raw/validated output mismatch"
        )
    if record["output_sha256"] != _sha256_json(output):
        raise FeedbackReviewArtifactError(
            "accepted output hash mismatch"
        )
    if record["feedback_kind"] != output["feedback_kind"]:
        raise FeedbackReviewArtifactError(
            "accepted feedback_kind/output mismatch"
        )

    _nonempty_text("feedback_kind", record["feedback_kind"])
    _nonempty_text("reviewer_id", record["reviewer_id"], maximum=128)
    _nonempty_text("generator_id", record["generator_id"])
    metadata = _mapping(
        "generation_metadata",
        record["generation_metadata"],
    )
    _reject_secret_metadata(metadata)
    _nonempty_text(
        "output_contract_version",
        record["output_contract_version"],
    )
    _strict_positive_int("word_count", record["word_count"])
    for field in ("generated_at", "reviewed_at", "accepted_at"):
        _timestamp(field, record[field])

    if candidate is not None:
        verified_candidate = verify_candidate_record(candidate)
        expected = {
            "prompt_sha256": verified_candidate["prompt_sha256"],
            "context_sha256": verified_candidate["context_sha256"],
            "feedback_kind": verified_candidate["feedback_kind"],
            "candidate_sha256": verified_candidate["candidate_sha256"],
            "generator_id": verified_candidate["generator_id"],
            "generation_metadata": verified_candidate["generation_metadata"],
            "raw_output": verified_candidate["raw_output"],
            "validated_output": verified_candidate["validated_output"],
            "output_contract_version": verified_candidate[
                "output_contract_version"
            ],
            "output_sha256": verified_candidate["output_sha256"],
            "word_count": verified_candidate["word_count"],
            "generated_at": verified_candidate["generated_at"],
        }
        for field, expected_value in expected.items():
            if record[field] != expected_value:
                raise FeedbackReviewArtifactError(
                    f"accepted {field} does not match candidate"
                )

    if review is not None:
        verified_review = verify_review_record(
            review,
            candidate=candidate,
        )
        if verified_review["decision"] != REVIEW_ACCEPT:
            raise FeedbackReviewArtifactError(
                "accepted artifact references a rejected review"
            )
        expected_review = {
            "prompt_sha256": verified_review["prompt_sha256"],
            "candidate_sha256": verified_review["candidate_sha256"],
            "review_sha256": verified_review["review_sha256"],
            "reviewer_id": verified_review["reviewer_id"],
            "reviewed_at": verified_review["reviewed_at"],
        }
        for field, expected_value in expected_review.items():
            if record[field] != expected_value:
                raise FeedbackReviewArtifactError(
                    f"accepted {field} does not match review"
                )
    return record


class FeedbackReviewArtifactStore:
    """Filesystem store with immutable, atomic candidate/review/accepted files."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def _candidate_path(
        self,
        prompt_sha256: str,
        candidate_sha256: str,
    ) -> Path:
        prompt_hash = _hex_digest("prompt_sha256", prompt_sha256)
        candidate_hash = _hex_digest(
            "candidate_sha256",
            candidate_sha256,
        )
        return (
            self.root
            / "candidates"
            / prompt_hash
            / f"{candidate_hash}.json"
        )

    def _review_path(self, candidate_sha256: str) -> Path:
        candidate_hash = _hex_digest(
            "candidate_sha256",
            candidate_sha256,
        )
        return self.root / "reviews" / f"{candidate_hash}.json"

    def _accepted_path(self, prompt_sha256: str) -> Path:
        prompt_hash = _hex_digest("prompt_sha256", prompt_sha256)
        return self.root / "accepted" / f"{prompt_hash}.json"

    @staticmethod
    def _read_json(path: Path) -> dict[str, object]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise FeedbackReviewArtifactError(
                f"feedback review artifact not found: {path}"
            ) from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise FeedbackReviewArtifactError(
                f"cannot read feedback review artifact: {path}"
            ) from exc
        if not isinstance(value, dict):
            raise FeedbackReviewArtifactError(
                f"feedback review artifact root is not an object: {path}"
            )
        return value

    @staticmethod
    def _write_once(path: Path, value: Mapping[str, object]) -> None:
        payload = _mapping("artifact", value)
        encoded = (
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
        path.parent.mkdir(parents=True, exist_ok=True)

        if path.exists():
            existing = FeedbackReviewArtifactStore._read_json(path)
            if existing == payload:
                return
            raise FeedbackReviewArtifactConflictError(
                f"immutable feedback artifact conflict: {path}"
            )

        temporary = path.parent / (
            f".{path.name}.{uuid4().hex}.tmp"
        )
        try:
            with temporary.open("xb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError:
                existing = FeedbackReviewArtifactStore._read_json(path)
                if existing != payload:
                    raise FeedbackReviewArtifactConflictError(
                        f"immutable feedback artifact conflict: {path}"
                    )
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                try:
                    os.fsync(directory_fd)
                except OSError:
                    # Directory fsync is not supported by every local
                    # filesystem. The fully written file and atomic hard-link
                    # publication remain authoritative.
                    pass
            finally:
                os.close(directory_fd)
        finally:
            temporary.unlink(missing_ok=True)

    def write_candidate(
        self,
        candidate: Mapping[str, object],
    ) -> Path:
        verified = verify_candidate_record(candidate)
        path = self._candidate_path(
            str(verified["prompt_sha256"]),
            str(verified["candidate_sha256"]),
        )
        self._write_once(path, verified)
        return path

    def load_candidate(
        self,
        prompt_sha256: str,
        candidate_sha256: str,
    ) -> dict[str, object]:
        return verify_candidate_record(
            self._read_json(
                self._candidate_path(
                    prompt_sha256,
                    candidate_sha256,
                )
            )
        )

    def write_review(
        self,
        review: Mapping[str, object],
    ) -> Path:
        detached_review = verify_review_record(review)
        candidate = self.load_candidate(
            str(detached_review["prompt_sha256"]),
            str(detached_review["candidate_sha256"]),
        )
        verified = verify_review_record(
            detached_review,
            candidate=candidate,
        )
        path = self._review_path(
            str(verified["candidate_sha256"])
        )
        self._write_once(path, verified)
        return path

    def load_review(
        self,
        prompt_sha256: str,
        candidate_sha256: str,
    ) -> dict[str, object]:
        candidate = self.load_candidate(
            prompt_sha256,
            candidate_sha256,
        )
        return verify_review_record(
            self._read_json(
                self._review_path(candidate_sha256)
            ),
            candidate=candidate,
        )

    def promote_accepted(
        self,
        *,
        prompt_sha256: str,
        candidate_sha256: str,
        accepted_at: str,
    ) -> Path:
        candidate = self.load_candidate(
            prompt_sha256,
            candidate_sha256,
        )
        review = self.load_review(
            prompt_sha256,
            candidate_sha256,
        )
        accepted = build_accepted_record(
            candidate=candidate,
            review=review,
            accepted_at=accepted_at,
        )
        path = self._accepted_path(prompt_sha256)
        self._write_once(path, accepted)
        return path

    def load_accepted(
        self,
        prompt_sha256: str,
    ) -> dict[str, object]:
        accepted = verify_accepted_record(
            self._read_json(
                self._accepted_path(prompt_sha256)
            )
        )
        candidate = self.load_candidate(
            prompt_sha256,
            str(accepted["candidate_sha256"]),
        )
        review = self.load_review(
            prompt_sha256,
            str(accepted["candidate_sha256"]),
        )
        return verify_accepted_record(
            accepted,
            candidate=candidate,
            review=review,
        )
