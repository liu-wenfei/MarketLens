from __future__ import annotations

import pytest

from marketlens.agents.activation.policy import (
    DEFAULT_ACTIVITY_BASELINES,
    ActivationConfig,
    ActivationPolicy,
    ActivationPolicyError,
)


def test_default_activity_baselines_are_heterogeneous_and_ordered():
    assert DEFAULT_ACTIVITY_BASELINES["低"] < DEFAULT_ACTIVITY_BASELINES["中"]
    assert DEFAULT_ACTIVITY_BASELINES["中"] < DEFAULT_ACTIVITY_BASELINES["高"]


def test_default_baselines_reproduce_a_020_source_weighted_mean():
    counts = {"低": 332, "中": 371, "高": 297}
    weighted = sum(DEFAULT_ACTIVITY_BASELINES[k] * counts[k] for k in counts) / 1000
    assert weighted == pytest.approx(0.20, abs=1e-12)


def test_recency_only_increases_propensity_and_saturates():
    policy = ActivationPolicy()
    fresh = policy.propensity(activity_category="中", steps_since_last_activation=0)
    delayed = policy.propensity(activity_category="中", steps_since_last_activation=3)
    saturated = policy.propensity(activity_category="中", steps_since_last_activation=500)
    cap_equivalent = policy.propensity(activity_category="中", steps_since_last_activation=5)

    assert fresh.p_active == pytest.approx(fresh.p_base)
    assert delayed.p_active > fresh.p_active
    assert saturated.p_active == pytest.approx(cap_equivalent.p_active)
    assert policy.config.p_min <= saturated.p_active <= policy.config.p_max


def test_policy_rejects_invalid_configuration_and_unknown_category():
    with pytest.raises(ActivationPolicyError):
        ActivationConfig(p_min=0.8, p_max=0.6)

    policy = ActivationPolicy()
    with pytest.raises(ActivationPolicyError, match="unsupported activity category"):
        policy.propensity(activity_category="unknown", steps_since_last_activation=0)
