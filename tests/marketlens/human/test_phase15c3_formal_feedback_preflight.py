from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


preflight = importlib.import_module(
    "marketlens.human.formal_feedback_preflight"
)


ROOT = Path(__file__).resolve().parents[3]
VALID_REFLECTION = " ".join(["reflection"] * 270)
SHORT_REFLECTION = " ".join(["short"] * 20)


class _FakeResponses:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        output = self.outputs.pop(0)
        return SimpleNamespace(
            id=f"resp-{len(self.calls)}",
            _request_id=f"req-{len(self.calls)}",
            model="gpt-5-nano",
            status="completed",
            output_text=output,
            usage=SimpleNamespace(
                input_tokens=300,
                output_tokens=350,
                total_tokens=650,
            ),
        )


class _FakeClient:
    def __init__(self, outputs):
        self.responses = _FakeResponses(outputs)


def _raw(reflection):
    return json.dumps(
        {
            "feedback_kind": "final_session_summary",
            "reflection": reflection,
        }
    )


def test_default_dry_run_reads_no_key_and_creates_no_files(
    tmp_path,
):
    output_root = tmp_path / "preflight"

    report = preflight.run_preflight(
        execute=False,
        acknowledge_paid_api_call=False,
        repo_root=ROOT,
        output_root=output_root,
        environ={
            "OPENAI_API_KEY": "must-not-be-read",
            "OPENAI_BASE_URL": "https://must-not-be-used.invalid",
        },
    )

    assert report["status"] == "DRY_RUN_READY"
    assert report["provider_request_made"] is False
    assert report["api_key_read"] is False
    assert report["maximum_provider_requests_if_executed"] == 2
    assert not output_root.exists()


def test_execute_requires_explicit_paid_acknowledgement(
    tmp_path,
):
    with pytest.raises(
        preflight.FormalFeedbackPreflightError,
        match="acknowledge-paid-api-call",
    ):
        preflight.run_preflight(
            execute=True,
            acknowledge_paid_api_call=False,
            repo_root=ROOT,
            output_root=tmp_path / "preflight",
            environ={"OPENAI_API_KEY": "not-real"},
            enforce_clean_tracked_state=False,
        )

    assert not (tmp_path / "preflight").exists()


def test_missing_key_or_custom_base_url_does_not_lock(
    tmp_path,
):
    output_root = tmp_path / "preflight"

    with pytest.raises(
        preflight.FormalFeedbackPreflightError,
        match="OPENAI_API_KEY",
    ):
        preflight.run_preflight(
            execute=True,
            acknowledge_paid_api_call=True,
            repo_root=ROOT,
            output_root=output_root,
            environ={},
            enforce_clean_tracked_state=False,
        )

    with pytest.raises(
        preflight.FormalFeedbackPreflightError,
        match="OPENAI_BASE_URL",
    ):
        preflight.run_preflight(
            execute=True,
            acknowledge_paid_api_call=True,
            repo_root=ROOT,
            output_root=output_root,
            environ={
                "OPENAI_API_KEY": "not-a-real-key",
                "OPENAI_BASE_URL": "https://example.invalid",
            },
            enforce_clean_tracked_state=False,
        )

    assert not output_root.exists()


def test_fake_execute_writes_lock_and_validated_receipt(
    tmp_path,
):
    output_root = tmp_path / "preflight"
    client = _FakeClient([_raw(VALID_REFLECTION)])
    captured = []

    def factory(**kwargs):
        captured.append(kwargs)
        return client

    receipt = preflight.run_preflight(
        execute=True,
        acknowledge_paid_api_call=True,
        repo_root=ROOT,
        output_root=output_root,
        environ={"OPENAI_API_KEY": "not-a-real-key"},
        client_factory=factory,
        enforce_clean_tracked_state=False,
    )

    assert receipt["status"] == "PREFLIGHT_VALIDATED"
    assert receipt["word_count"] == 270
    assert receipt["participant_db_touched"] is False
    assert receipt["formal_experimental_evidence"] is False
    assert (
        receipt["generation_metadata"]["attempt_count"]
        == 1
    )
    assert captured == [
        {
            "api_key": "not-a-real-key",
            "max_retries": 0,
            "timeout": 45.0,
        }
    ]
    assert len(client.responses.calls) == 1

    lock_path = output_root / preflight.EXECUTION_LOCK_NAME
    success_path = output_root / preflight.SUCCESS_RECEIPT_NAME
    assert lock_path.is_file()
    assert success_path.is_file()
    assert not (
        output_root / preflight.FAILURE_RECEIPT_NAME
    ).exists()

    combined = (
        lock_path.read_text(encoding="utf-8")
        + success_path.read_text(encoding="utf-8")
    )
    assert "not-a-real-key" not in combined

    with pytest.raises(
        preflight.FormalFeedbackPreflightError,
        match="execution lock exists",
    ):
        preflight.run_preflight(
            execute=True,
            acknowledge_paid_api_call=True,
            repo_root=ROOT,
            output_root=output_root,
            environ={"OPENAI_API_KEY": "not-a-real-key"},
            client_factory=factory,
            enforce_clean_tracked_state=False,
        )

    assert len(client.responses.calls) == 1


def test_validation_failure_uses_two_requests_and_locks(
    tmp_path,
):
    output_root = tmp_path / "preflight"
    client = _FakeClient(
        [
            _raw(SHORT_REFLECTION),
            _raw(SHORT_REFLECTION),
        ]
    )

    with pytest.raises(Exception):
        preflight.run_preflight(
            execute=True,
            acknowledge_paid_api_call=True,
            repo_root=ROOT,
            output_root=output_root,
            environ={"OPENAI_API_KEY": "not-a-real-key"},
            client_factory=lambda **kwargs: client,
            enforce_clean_tracked_state=False,
        )

    assert len(client.responses.calls) == 2
    assert (
        output_root / preflight.EXECUTION_LOCK_NAME
    ).is_file()
    failure_path = output_root / preflight.FAILURE_RECEIPT_NAME
    assert failure_path.is_file()
    failure = json.loads(
        failure_path.read_text(encoding="utf-8")
    )
    assert failure["status"] == "FAILED_CLOSED"
    assert failure["fallback_used"] is False
    assert failure["participant_db_touched"] is False
    assert not (
        output_root / preflight.SUCCESS_RECEIPT_NAME
    ).exists()
