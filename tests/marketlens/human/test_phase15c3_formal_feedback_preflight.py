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


def test_missing_key_does_not_lock(
    tmp_path,
):
    output_root = tmp_path / "preflight"

    with pytest.raises(
        preflight.FormalFeedbackPreflightError,
        match="API key",
    ):
        preflight.run_preflight(
            execute=True,
            acknowledge_paid_api_call=True,
            repo_root=ROOT,
            output_root=output_root,
            environ={},
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
            "timeout": 30.0,
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
    assert failure["fallback_used"] is True
    assert failure["generation_metadata"]["attempt_count"] == 2
    assert failure["participant_db_touched"] is False
    assert not (
        output_root / preflight.SUCCESS_RECEIPT_NAME
    ).exists()



def test_v3_environment_key_is_required(tmp_path):
    resolved, metadata = preflight._resolve_provider_environment(
        repo_root=ROOT,
        source={"OPENAI_API_KEY": "environment-key"},
        expected_model="gpt-5-nano",
        provider_config_path=tmp_path / "ignored-feedback.yaml",
    )

    assert resolved["OPENAI_API_KEY"] == "environment-key"
    assert "OPENAI_BASE_URL" not in resolved
    assert metadata["credential_source"] == "OPENAI_API_KEY"
    assert metadata["config_present"] is False


def test_v3_custom_compatible_base_url_is_allowed(tmp_path):
    resolved, metadata = preflight._resolve_provider_environment(
        repo_root=ROOT,
        source={
            "OPENAI_API_KEY": "environment-key",
            "OPENAI_BASE_URL": "https://compatible.example/v1",
        },
        expected_model="gpt-5-nano",
        provider_config_path=tmp_path / "ignored-feedback.yaml",
    )

    assert resolved["OPENAI_API_KEY"] == "environment-key"
    assert (
        resolved["OPENAI_BASE_URL"]
        == "https://compatible.example/v1"
    )
    assert (
        metadata["provider_base_url"]
        == "https://compatible.example/v1"
    )
    assert metadata["credential_source"] == "OPENAI_API_KEY"


def test_v4_local_yaml_provider_config_is_loaded(tmp_path):
    config_path = tmp_path / "feedback.local.yaml"
    config_path.write_text(
        'provider: "openai_compatible"\n'
        'api_key: "yaml-local-key"\n'
        'base_url: "https://compatible.example/v1"\n'
        'model_name: "compatible-model"\n',
        encoding="utf-8",
    )

    resolved, metadata = (
        preflight._resolve_provider_environment(
            repo_root=ROOT,
            source={},
            expected_model="gpt-5-nano",
            provider_config_path=config_path,
        )
    )

    assert resolved["OPENAI_API_KEY"] == "yaml-local-key"
    assert (
        resolved["OPENAI_BASE_URL"]
        == "https://compatible.example/v1"
    )
    assert resolved["OPENAI_MODEL"] == "compatible-model"

    assert metadata["credential_source"] == (
        "feedback.local.yaml:api_key"
    )
    assert metadata["requested_model"] == "compatible-model"
    assert metadata["config_present"] is True


def test_v3_failure_receipt_has_sanitised_root_cause(tmp_path):
    class ProviderFailure(RuntimeError):
        status_code = 401
        code = "invalid_api_key"
        request_id = "req-sanitised"

    class FailingResponses:
        def create(self, **kwargs):
            raise ProviderFailure("must not be persisted")

    class FailingClient:
        responses = FailingResponses()

    output_root = tmp_path / "preflight"

    with pytest.raises(Exception):
        preflight.run_preflight(
            execute=True,
            acknowledge_paid_api_call=True,
            repo_root=ROOT,
            output_root=output_root,
            environ={"OPENAI_API_KEY": "environment-key"},
            client_factory=lambda **kwargs: FailingClient(),
            enforce_clean_tracked_state=False,
        )

    failure_path = (
        output_root / preflight.FAILURE_RECEIPT_NAME
    )
    failure = json.loads(
        failure_path.read_text(encoding="utf-8")
    )
    assert failure["provider_diagnostic"] == {
        "provider_error_type": "ProviderFailure",
        "provider_status_code": 401,
        "provider_error_code": "invalid_api_key",
        "provider_request_id": "req-sanitised",
    }
    combined = (
        (output_root / preflight.EXECUTION_LOCK_NAME)
        .read_text(encoding="utf-8")
        + failure_path.read_text(encoding="utf-8")
    )
    assert "environment-key" not in combined
    assert "must not be persisted" not in combined
