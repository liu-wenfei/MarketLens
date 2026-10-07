# MarketLens

### Human-AI Multi-Agent Financial Decision Environment

MarketLens is a web-based financial decision simulation platform where participants interact with a dynamic LLM-agent market, make repeated investment judgements and simulated trades, receive new evidence, and decide whether to revise their views over time.

**60 participants** · **60/60 completed sessions** · **180/180 feedback delivered** · **755/755 regression tests passed**

<p align="center">
  <img src="docs/images/marketlens_market_overview.png" alt="MarketLens market overview" width="100%">
</p>

---

## Why MarketLens?

A trade alone does not reveal how a person reached a decision. Someone may change their judgement without trading, or trade without changing their stated view.

MarketLens therefore captures the full decision chain:

**Information → Judgement → Confidence → Evidence → Action → New Information → Revision → Reflection**

For each formal judgement, the platform records the user's stated view, confidence, evidence, rationale, portfolio action and information exposure, making it possible to compare **what users think** with **what they actually do**.

---


## Product Scope & Ownership

MarketLens is designed as a **dynamic Human-AI financial decision environment** where users continuously interact with evolving Agent behaviour, market information, community activity and simulated portfolio state.

The product goal is not to predict stock prices or automate investment decisions. It is to create a persistent environment where users can:

**Observe → Judge → Act → Receive New Information → Revise → Reflect**

### Product Vision

The target experience is a continuously evolving market in which:

- LLM Agents update beliefs and behaviours over time
- market and community information changes dynamically
- users make repeated judgements rather than one-off predictions
- users can trade, observe consequences and revise their views
- system state, information exposure and user actions remain traceable

### MVP Strategy

The first MVP deliberately used **frozen canonical Agent episodes** for participant replay.

This was a validation decision, not the final product model.

Freezing the Agent trajectory made it possible to first verify:

- the full Human-AI decision loop
- frontend/backend state consistency
- participant isolation
- controlled information release
- judgement and trading capture
- feedback delivery
- end-to-end observability

Once this core loop is stable, the product can progressively move toward more live and adaptive Agent-market interaction.

**Product direction: Controlled MVP → Dynamic Runtime → Richer Human-Agent Interaction**

### Product Architecture

MarketLens combines a dynamic Multi-Agent market environment with a human-facing decision layer.

| Layer | Role |
|---|---|
| **Agent Environment** | Generates market behaviour, trading activity and social interaction |
| **Market Dynamics** | Provides evolving prices, information and community context |
| **Human Interaction** | Supports repeated judgement, simulated trading and reflection |
| **Participant State** | Maintains session, cash, holdings, orders, judgement and feedback |
| **Information Control** | Governs what information becomes visible at each decision state |
| **Measurement** | Tracks exposure, confidence, judgement, rationale, action and position |
| **Reliability** | Applies state validation, isolation, guardrails, retry and fallback |
| **Evaluation** | Measures both system reliability and Human-AI interaction outcomes |


---


## Product Experience

Each participant completes a continuous 15-period financial decision journey with five formal judgement checkpoints.

| Checkpoint | User task |
|---|---|
| **J0** | Form an initial judgement |
| **J1** | Reassess after new unverified information |
| **J2** | Reassess after continued market activity |
| **J3** | Respond immediately after authoritative correction |
| **J4** | Form a final judgement after subsequent market activity |

Core journey:

**Market Context → Judgement → Simulated Trade → New Information → Correction → Judgement Update → Reflection**

---

## How It Works

MarketLens combines two layers.

<p align="center">
  <img src="docs/images/marketlens_architecture.png" alt="MarketLens system architecture" width="100%">
</p>

### Multi-Agent Market

The formal environment uses **30 financial agents**:

- 12 Fundamental agents
- 18 Technical agents

Agents maintain differentiated strategies, beliefs, behavioural characteristics and portfolio states. Their decision process follows a BDI-style loop:

**Belief → Desire → Intention → Action → Environment Response → Belief Update**

### Human Participant Layer

Participants share the simulated market context but maintain independent:

- sessions
- cash
- holdings
- judgements
- orders
- feedback
- event histories

Participant trades affect only the participant ledger and do **not** change the canonical Agent world.

**Shared Environment Context + Independent Participant State**

---

## Source of Truth, Context & State Architecture

MarketLens separates **reasoning**, **authoritative state** and **participant interaction** rather than allowing the LLM to control the whole system.

### Authoritative State

The backend is the source of truth for session progression, financial state, information release and participant records.

| Component | Responsibility | Product boundary |
|---|---|---|
| **Canonical Agent World** | Agent activity, market state, prices, news and visible forum context | Frozen per canonical episode; participants do not modify it |
| **Participant Runtime** | Period, judgement, confidence, cash, holdings, orders, portfolio, feedback and session state | Isolated per participant/session |
| **Controlled Stimulus Layer** | Unverified information, correction and release timing | Released only when protocol state allows |
| **Event / Provenance Records** | Exposure, judgement, order, execution and feedback events | Used to reconstruct the decision path |
| **Frontend** | Presents current state and submits user actions | Does not independently derive price, cash, position, period or checkpoint |
| **LLM / Agent Reasoning** | Semantic interpretation, market reasoning, belief update and reflective feedback | Never acts as the source of truth for exact financial or protocol state |

This creates a simple rule:

> **Reasoning can be probabilistic; financial and experimental state cannot be.**

### Context Model

Context is divided by lifecycle and responsibility rather than treated as one continuously growing prompt.

| Context layer | Examples | Lifecycle |
|---|---|---|
| **Static Profile** | Persona, strategy, behavioural attributes, social attributes | Relatively stable |
| **Dynamic State** | Belief, cash, holdings, portfolio, previous actions, historical performance | Updated over time |
| **Turn Context** | Current market, news, visible posts, task, available assets and constraints | Current tick / task |
| **Participant Session State** | Period, exposure history, judgement, confidence, orders, portfolio and feedback status | Persisted per session |

The retrieval path is:

**Hard Filter → Candidate Retrieval → Context Assembly → LLM**

Participant, session, episode, period, timestamp and information-access constraints are enforced before semantic relevance is considered.

> **Deterministic boundary first, semantic relevance second.**

### End-to-End Decision Trace

Measurement is part of the architecture rather than an after-the-fact analytics layer.

**Exposure → Judgement → Confidence → Evidence → Reason → Order → Execution → Position → Feedback**

Records are correlated using participant, session, episode, period and checkpoint identifiers, allowing the system to reconstruct what information a participant had seen before a judgement or trade.

This is also why MarketLens stores **judgement and action separately**: a participant can change their view without trading, or trade without changing the formal judgement.

---


## Reliability by Design

### Trading Guardrails

Trading actions are checked against deterministic constraints including:

- available cash
- current holdings
- valid price
- valid action
- position limits
- no short selling

The order flow separates preview from execution so that a proposed trade can be inspected before it changes portfolio state.

<p align="center">
  <img src="docs/images/marketlens_order_preview.png" alt="MarketLens order preview and execution guardrail" width="100%">
</p>

### Session Isolation

Each participant has an independent ledger and session state. One participant cannot alter another participant's portfolio, judgement history or feedback.

### Feedback Reliability

Reflective feedback follows:

**Authoritative Records → Deterministic Statistics → Bounded Context → LLM → Validation → Retry → Validated Output / Fallback**

Formal deployment delivered **180 / 180 feedback responses**, including:

- **152 validated live-provider responses**
- **28 validated fallback responses**

> **Validated fallback > invalid AI output > broken user flow**

---

## Data & Runtime Model

MarketLens combines three data layers:

- **Agent-generated environment** — simulated market activity, prices, news and community context produced by the underlying Multi-Agent environment
- **Controlled product information** — information released according to the current session and decision state
- **User interaction records** — judgement, confidence, evidence, rationale, orders, execution, position and feedback

The current MVP uses generated-and-frozen Agent episodes to make early validation reproducible. The broader product direction is a more dynamic runtime while retaining the same state, safety and observability boundaries.

MarketLens does not present its simulated prices or Agent-generated narratives as live financial-market data.

---


## Evaluation

MarketLens uses system-level release gates rather than relying on one model metric.

### Agent Activity

Population adequacy was tested across **100 fixed seeds × 27 simulation ticks**.

| Population | Zero-active critical trajectories | Minimum mean active agents | Decision |
|---|---:|---:|---|
| N20 | 9 / 100 | 3.88 | Fail |
| N30 | 0 / 100 | 6.26 | Pass |

N30 was selected for the formal environment.

### Trading Validation

Across 27 research-relevant trading paths, **111 / 111 order requests executed** under both 0 bps and 10 bps transaction-cost settings.

### Session Integrity

Formal audit confirmed:

- **60 / 60 completed sessions**
- **60 / 60 completed all 15 periods**
- **60 unique sessions**
- **60 / 60 completed J0–J4**
- complete participant-visible histories

### Regression

The frozen release completed **755 / 755 automated regression tests passed**.

---

> **Evidence boundary:** behavioural metrics are calculated from formal MarketLens participant-session records, while Agent-market activity metrics come from canonical episode and validation runs. The **755 / 755 regression result applies to the frozen documented release**. Formal participant sessions did not persist an immutable per-session build identifier, so this repository does not claim that every participant session ran on that exact final commit.

## MVP Validation

The first MVP was validated with **60 participants** across the full 15-period decision journey, with **60 / 60 sessions completed**. The frozen documented release also passed **755 / 755 retained regression tests**.

The validation supported one key measurement principle:

> **Attention ≠ Judgement Change ≠ Behaviour Change**

MarketLens therefore keeps information exposure, confidence, judgement and action as separate product signals.

This validation demonstrates that the core interaction and measurement model works end to end; it does not define the final dynamic runtime.

---


## Product Decisions & Trade-offs

MarketLens prioritises a complete and traceable Human-AI decision loop over maximum Agent autonomy.

**MVP priority: Decision Loop → State Consistency → Record Integrity → AI Richness**

| Trade-off | Decision | Why |
|---|---|---|
| **Dynamic Product vs MVP Comparability** | MVP: generated Agent environment → frozen episode replay; future: progressively more live Agent interaction | Validate the Human-AI loop first, then increase runtime dynamism without losing state integrity |
| **AI Autonomy vs Reliability** | LLM for reasoning; deterministic code for financial and protocol state | Cash, holdings, settlement and session progression cannot depend on probabilistic model output |
| **Semantic Retrieval vs State Control** | Hard Filter → Candidate Retrieval → Context Assembly | Time, session, access and protocol boundaries matter more than semantic similarity |
| **Personalisation vs Flow Stability** | Live feedback + validation + retry + fallback | Personalisation should not be allowed to break the participant journey |
| **Agent Richness vs Runtime** | Select N30 through explicit activity gates | Use enough Agents to sustain a heterogeneous environment without adding complexity for its own sake |
| **Participant Influence vs Environment Integrity** | Participant trades affect only the participant ledger | Sacrifice some market interactivity to preserve comparability, traceability and reproducibility |

### MVP to Dynamic Runtime

The frozen canonical-episode approach is an **MVP validation mode**, not the intended end state of MarketLens.

The product direction is:

**Generated Agent Environment → Validated Human-AI Loop → Increasingly Dynamic Runtime → Richer Human-Agent Interaction**

The key requirement is that greater Agent autonomy must not break session state, financial-state correctness, information boundaries or traceability.


> **Reliability first, autonomy second.**

---


## Technical Details

<details>
<summary><strong>Open technical implementation, repository, privacy and attribution details</strong></summary>

### Tech Stack

**Frontend:** React · TypeScript · Vite

**Backend:** Python · FastAPI · SQLite · SQLAlchemy

**AI / Agent:** LLM-driven agents · BDI-style reasoning · Tool-use · Structured output validation · Bounded context assembly · Embedding support · Retry / fallback runtime

**Evaluation:** pytest · deterministic protocol audits · population-sensitivity testing · trajectory validation · participant/session audits

---

### Repository Structure

```text
MarketLens/
├── frontend/              # Participant-facing React application
├── marketlens/
│   ├── agents/
│   ├── episode/
│   ├── experiment/
│   ├── human/
│   ├── information/
│   ├── market/
│   ├── measurement/
│   ├── persistence/
│   ├── stimulus/
│   └── validation/
├── scripts/
├── tests/
├── data/
├── docs/
└── trader/
```

---

### Local Development

Create the Python environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-marketlens-backend.txt
```

Install frontend dependencies:

```bash
cd frontend
npm install
```

Provider-specific configuration should be created locally and must not be committed.

---

### Research Data and Privacy

Formal participant credentials and participant runtime databases are intentionally excluded from the public repository.

The public repository contains simulation assets required for reproducibility, while participant-private study data remain local.

MarketLens is a research simulation environment and does not provide financial advice or live trading services.

---

### Research Context

MarketLens was developed as part of an MSc Applied Artificial Intelligence dissertation at the University of Warwick.

The project studies how participants revise financial judgements following corrective evidence within a continuing LLM-agent financial information environment.

---

### Upstream Attribution

MarketLens uses **TwinMarket** as the underlying LLM-agent financial simulation environment.

TwinMarket was developed by Yuzhe Yang, Yifei Zhang, Minghao Wu, Kaidi Zhang, Yunmiao Zhang, Honghai Yu, Yan Hu and Benyou Wang, and was accepted at NeurIPS 2025.

The original upstream README is retained at:

`docs/upstream/TWINMARKET_ORIGINAL_README.md`

MarketLens-specific work focuses on the human-participant product layer, controlled information flow, participant state, interaction design, evaluation, validation and formal deployment.

---

</details>

---

## License

This repository retains the applicable MIT License.

Please also refer to the original TwinMarket project and authors when reusing the underlying simulation components.
