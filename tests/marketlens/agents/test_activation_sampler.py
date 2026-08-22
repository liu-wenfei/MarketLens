from __future__ import annotations

from marketlens.agents.activation.policy import ActivationPolicy
from marketlens.agents.activation.profiles import AgentActivationProfile
from marketlens.agents.activation.sampler import sample_activation
from marketlens.agents.activation.state import ActivationState


def _profiles():
    return [
        AgentActivationProfile("1", "低"),
        AgentActivationProfile("2", "中"),
        AgentActivationProfile("3", "高"),
        AgentActivationProfile("4", "中"),
    ]


def test_sampling_is_reproducible_and_order_independent():
    policy = ActivationPolicy()
    state = ActivationState({"1": 1, "2": 2, "3": 3, "4": 4})

    a = sample_activation(_profiles(), policy=policy, state=state, seed="abc", step=7)
    b = sample_activation(reversed(_profiles()), policy=policy, state=state, seed="abc", step=7)

    assert a == b


def test_agent_specific_probabilities_are_heterogeneous():
    batch = sample_activation(
        _profiles(), policy=ActivationPolicy(), state=ActivationState(), seed="x", step=0
    )
    probabilities = {r.activity_category: r.propensity.p_active for r in batch.results[:3]}

    assert probabilities["低"] < probabilities["中"] < probabilities["高"]


def test_state_resets_active_agents_and_increments_inactive_agents():
    policy = ActivationPolicy()
    batch = sample_activation(
        _profiles(), policy=policy, state=ActivationState(), seed="state-test", step=0
    )
    active = set(batch.active_agent_ids)

    for profile in _profiles():
        value = batch.next_state.steps_for(profile.user_id)
        assert value == (0 if profile.user_id in active else 1)


def test_sparse_smoke_run_does_not_activate_every_agent():
    profiles = [
        AgentActivationProfile(str(i), ("低", "中", "高")[i % 3])
        for i in range(1, 101)
    ]
    batch = sample_activation(
        profiles,
        policy=ActivationPolicy(),
        state=ActivationState(),
        seed="phase04-smoke",
        step=0,
    )

    assert 0 < len(batch.active_agent_ids) < len(profiles)
    assert len(batch.active_agent_ids) <= 50
