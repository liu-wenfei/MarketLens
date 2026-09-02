"""Local/deployment configuration for formal feedback providers.

Secrets may live in the Git-ignored config/feedback.local.yaml file or be
overridden by environment variables. No secret value is included in metadata
or object representations.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Mapping

import yaml


LOCAL_PROVIDER_CONFIG_RELATIVE = Path(
    "config/feedback.local.yaml"
)

DEFAULT_PROVIDER = "openai_compatible"
DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-5-nano"


class FormalProviderConfigError(ValueError):
    """Raised when local/deployment provider configuration is invalid."""


@dataclass(frozen=True, slots=True)
class ResolvedFormalProviderConfig:
    provider: str
    api_key: str
    base_url: str
    model_name: str
    credential_source: str
    config_present: bool
    config_path: str | None
    base_url_explicit: bool

    def __repr__(self) -> str:
        return (
            "ResolvedFormalProviderConfig("
            f"provider={self.provider!r}, "
            "api_key=<REDACTED>, "
            f"base_url={self.base_url!r}, "
            f"model_name={self.model_name!r}, "
            f"credential_source={self.credential_source!r}, "
            f"config_present={self.config_present!r}, "
            f"config_path={self.config_path!r}, "
            f"base_url_explicit={self.base_url_explicit!r})"
        )

    def environment(self) -> dict[str, str]:
        result = {
            "OPENAI_API_KEY": self.api_key,
            "OPENAI_MODEL": self.model_name,
        }
        if self.base_url_explicit:
            result["OPENAI_BASE_URL"] = self.base_url
        return result

    def metadata(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "credential_source": self.credential_source,
            "config_present": self.config_present,
            "config_path": self.config_path,
            "provider_base_url": self.base_url,
            "requested_model": self.model_name,
        }


def _normalise_optional_string(
    value: object,
    *,
    field: str,
) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise FormalProviderConfigError(
            f"{field} must be a string or null"
        )
    return value.strip()


def resolve_formal_provider_config(
    *,
    repo_root: Path | None = None,
    environ: Mapping[str, str] | None = None,
    provider_config_path: Path | None = None,
    allow_local_file: bool = True,
    default_model: str = DEFAULT_MODEL,
) -> ResolvedFormalProviderConfig:
    source = os.environ if environ is None else environ

    root = (
        Path(repo_root)
        if repo_root is not None
        else Path(__file__).resolve().parents[3]
    )

    config_path = (
        Path(provider_config_path)
        if provider_config_path is not None
        else root / LOCAL_PROVIDER_CONFIG_RELATIVE
    )

    payload: Mapping[str, object] = {}
    config_present = False

    if allow_local_file and config_path.is_file():
        try:
            loaded = yaml.safe_load(
                config_path.read_text(encoding="utf-8")
            )
        except (OSError, yaml.YAMLError) as exc:
            raise FormalProviderConfigError(
                "unable to read formal feedback provider configuration"
            ) from exc

        if loaded is None:
            loaded = {}

        if not isinstance(loaded, Mapping):
            raise FormalProviderConfigError(
                "formal feedback provider configuration must be a mapping"
            )

        payload = loaded
        config_present = True

    provider = _normalise_optional_string(
        payload.get("provider"),
        field="provider",
    ) or DEFAULT_PROVIDER

    if provider not in {
        "openai",
        "openai_compatible",
    }:
        raise FormalProviderConfigError(
            "provider must be openai or openai_compatible"
        )

    environment_key = _normalise_optional_string(
        source.get("OPENAI_API_KEY"),
        field="OPENAI_API_KEY",
    )

    yaml_key = _normalise_optional_string(
        payload.get("api_key"),
        field="api_key",
    )

    if environment_key:
        api_key = environment_key
        credential_source = "OPENAI_API_KEY"
    elif yaml_key:
        api_key = yaml_key
        credential_source = "feedback.local.yaml:api_key"
    else:
        raise FormalProviderConfigError(
            "formal feedback API key is required"
        )

    if any(char.isspace() for char in api_key):
        raise FormalProviderConfigError(
            "formal feedback API key contains whitespace"
        )

    environment_base_url = _normalise_optional_string(
        source.get("OPENAI_BASE_URL"),
        field="OPENAI_BASE_URL",
    ).rstrip("/")

    yaml_base_url = _normalise_optional_string(
        payload.get("base_url"),
        field="base_url",
    ).rstrip("/")

    if environment_base_url:
        base_url = environment_base_url
        base_url_explicit = True
    elif yaml_base_url:
        base_url = yaml_base_url
        base_url_explicit = True
    else:
        base_url = DEFAULT_BASE_URL
        base_url_explicit = False

    if not (
        base_url.startswith("https://")
        or base_url.startswith("http://")
    ):
        raise FormalProviderConfigError(
            "formal feedback base_url must use http or https"
        )

    environment_model = _normalise_optional_string(
        source.get("OPENAI_MODEL"),
        field="OPENAI_MODEL",
    )

    yaml_model = _normalise_optional_string(
        payload.get("model_name"),
        field="model_name",
    )

    model_name = (
        environment_model
        or yaml_model
        or str(default_model).strip()
    )

    if not model_name:
        raise FormalProviderConfigError(
            "formal feedback model_name is required"
        )

    return ResolvedFormalProviderConfig(
        provider=provider,
        api_key=api_key,
        base_url=base_url,
        model_name=model_name,
        credential_source=credential_source,
        config_present=config_present,
        config_path=(
            str(config_path)
            if config_present
            else None
        ),
        base_url_explicit=base_url_explicit,
    )
