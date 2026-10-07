# MarketLens

### Human-AI Multi-Agent Financial Decision Environment

MarketLens is a web-based financial decision simulation platform where users interact with a dynamic LLM-agent market, make repeated investment judgements and simulated trades, receive new information, and decide whether to revise their views and actions over time.

Unlike a conventional trading simulator that focuses mainly on portfolio outcomes, MarketLens captures the full decision process:

**Information → Judgement → Confidence → Action → New Information → Revision → Reflection**

**Validated MVP:** 60 / 60 participant sessions completed · 755 / 755 retained regression tests passed

<p align="center">
  <img src="docs/images/marketlens_market_overview.png" alt="MarketLens market overview" width="100%">
</p>

## Product Demo

A walkthrough of the MarketLens Human-AI decision journey — from market observation and judgement to simulated trading, new information and decision revision.

<p align="center">
  <a href="https://www.youtube.com/watch?v=XQXaM8Aws8o">
    <img src="https://img.youtube.com/vi/XQXaM8Aws8o/hqdefault.jpg" alt="Watch the MarketLens Product Demo" width="720">
  </a>
</p>

---

## What MarketLens Does

Users enter a continuously evolving simulated financial environment where LLM Agents interpret information, update beliefs, trade and interact socially.

During a session, users:

1. observe changing market, company, news and community information
2. form a BUY / HOLD / SELL judgement
3. record confidence, evidence and reasoning
4. make or skip a simulated trade
5. observe subsequent market activity
6. receive new information
7. revise or maintain their judgement
8. reflect on how their reasoning and behaviour changed

MarketLens records both **what users think** and **what they actually do**, so judgement, confidence and behaviour can be measured separately rather than reducing the experience to a final trade.

> **Attention ≠ Judgement Change ≠ Behaviour Change**

---

## Key Product Capabilities

| Capability | What MarketLens Does |
|---|---|
| **Dynamic Agent Market** | LLM Agents interpret information, update beliefs, trade and interact within a changing market and social environment |
| **Continuous Decision Journey** | Users repeatedly observe, judge, act and revise decisions rather than completing a one-off prediction task |
| **Simulated Trading** | Users can preview and execute trades while cash, holdings and portfolio state are updated deterministically |
| **Independent User State** | Each user maintains an isolated session, portfolio, judgement history, orders and feedback state |
| **Controlled Information** | Information becomes visible according to simulation time, session state and access rules |
| **Decision Trace** | Exposure, confidence, evidence, rationale, action and position can be connected across the full journey |
| **Reflective AI Feedback** | LLM feedback supports reflection without acting as an investment adviser |
| **Guardrails & Validation** | Deterministic checks protect financial state, protocol progression and user isolation |

---

## Market & Information Sources

MarketLens operates on a simulated financial environment grounded in historical real-world data and dynamically generated market activity.

| Data Layer | Source / Generation | Role |
|---|---|---|
| **Historical stock & fundamental data** | CSMAR · 2023 SSE 50 data | Grounds the initial market and company state |
| **Market & economic news** | Sina · 10jqka | Provides historical market and economic information |
| **Company announcements** | CNINFO | Provides company-specific public information |
| **Investor behaviour data** | Xueqiu · Guba | Supports Agent profile and behavioural grounding |
| **Runtime prices & volume** | Simulated order-driven market | Evolves dynamically from Agent trading |
| **Runtime technical indicators** | Calculated from simulated market state | Supports Agent technical analysis as the market evolves |
| **Controlled product information** | MarketLens session / protocol layer | Releases information according to the current decision state |
| **User interaction records** | Generated inside MarketLens | Captures judgement, confidence, rationale, orders, execution, position and feedback |

Historical data **grounds the environment**. Once the simulation is running, prices, trading volume and derived technical indicators evolve from simulated Agent trading rather than replaying live financial-market data.

MarketLens does **not** present simulated prices or Agent-generated narratives as live market information.

---

## How It Works

**Multi-Agent Market → Human Decision Layer → Measurement & Reliability Layer**

<p align="center">
  <img src="docs/images/marketlens_architecture.png" alt="MarketLens system architecture" width="100%">
</p>

### Multi-Agent Market

The formal environment uses 30 financial Agents: 12 Fundamental Agents and 18 Technical Agents. Agents operate with different strategies, personas, beliefs and behavioural characteristics.

The bounded Agent loop is:

**Belief → Desire → Intention → Action → Environment Response → Belief Update**

Agents can consume market/news information, trade and interact through the simulated social environment. Execution remains bounded by the simulation clock and stage lifecycle rather than running as an unlimited autonomous loop.

### Human Decision Layer

Users share the same market context but maintain independent cash, holdings, orders, portfolio state, judgements and confidence records.

User actions do not rewrite another user's state. In the current MVP, user trades also do not modify the canonical Agent world, preserving reliable replay and evaluation.

---

## Context & State

| Context Layer | Examples | Lifecycle |
|---|---|---|
| **Static Profile** | Persona, strategy, behavioural attributes | Relatively stable |
| **Dynamic Agent State** | Belief, portfolio, previous actions, historical performance | Updated over time |
| **Turn Context** | Current market, news, visible posts, task and constraints | Current interaction |
| **User Session State** | Period, exposure history, judgement, confidence, orders, portfolio and feedback | Persisted per session |

Context assembly follows:

**Hard Filter → Candidate Retrieval → Context Assembly → LLM**

Time, session, episode, permission and protocol boundaries are enforced before semantic relevance is considered.

> **Deterministic boundary first, semantic relevance second.**

Embedding support is used for semantic representation / retrieval where appropriate; the current implementation is **not presented as a complete RAG pipeline**.

---

## Agent Harness & Evaluation

MarketLens evaluates the Agent product as a system rather than reducing quality to a single model metric.

| Harness Layer | MarketLens Implementation |
|---|---|
| **Reasoning & Planning** | BDI-style reasoning structures Agent beliefs, goals, intentions and actions |
| **Bounded Execution** | Agent actions run within a controlled tick / stage lifecycle |
| **Context & State** | Static profile, dynamic state, current-turn context and isolated user session state |
| **Retrieval & Assembly** | Hard state/access filters before candidate retrieval and semantic relevance |
| **Tools & Actions** | Market/news query, trading and social interaction capabilities |
| **Action Guardrails** | Cash, holdings, valid-price, valid-action, no-short and position constraints |
| **Isolation** | User state remains separated from other users and the canonical Agent environment |
| **Structured Output** | Model outputs pass schema and content validation before use |
| **Retry / Fallback** | Invalid feedback is retried and can fall back to a validated response |
| **Observability** | Agent context, actions, state transitions and failures can be traced |
| **Auditability** | Exposure, judgement, order, execution and position can be linked into an end-to-end decision trace |

### Release Gates

| Dimension | Validation Evidence |
|---|---|
| **Agent Activity** | N30 passed the activity gate: 0 / 100 zero-active critical trajectories; minimum mean active 6.26 |
| **Live Execution** | Bounded live-backend continuity validated |
| **Episode Integrity** | 27 ticks and 193 Agent pipeline executions per canonical episode |
| **Trading / Actions** | 111 / 111 relevant orders executed at both 0 and 10 bps |
| **Session Integrity** | 60 / 60 formal sessions completed |
| **Regression Stability** | 755 / 755 retained tests passed |

---

## Reliability & Product Boundaries

| Product Risk | Design Decision |
|---|---|
| **LLM modifies exact financial state** | LLM handles reasoning; deterministic code controls price, cash, holdings, settlement and execution |
| **Incorrect information appears too early** | Simulation date, protocol state and access boundaries control information release |
| **One user affects another user's state** | Session, portfolio, judgement and event state are isolated |
| **User action contaminates the Agent environment** | MVP user trades affect only the user's simulated ledger |
| **Invalid AI feedback breaks the journey** | Authoritative records → bounded context → LLM → validation → retry → validated fallback |
| **Semantic retrieval crosses hard boundaries** | Session, time and permission filters run before semantic retrieval |
| **Frontend and backend disagree on state** | Backend remains authoritative for price, position, cash, period and checkpoint |

<p align="center">
  <img src="docs/images/marketlens_order_preview.png" alt="MarketLens order preview and trading guardrail" width="100%">
</p>

> **Reliability first, autonomy second.**

---

## MVP Validation

The first MVP was validated with **60 participants** across the complete 15-period decision journey.

**60 / 60 sessions completed** · **755 / 755 retained regression tests passed**

The participant validation confirmed that the core loop can run end to end:

**Information → Judgement → Action → New Information → Revision → Trace**

The participant study validates the current interaction and measurement model; it does not define the final MarketLens runtime.

---

## Product Direction

MarketLens is designed as a **dynamic Human-AI decision environment**.

The current frozen canonical-episode workflow is an MVP validation mode used to stabilise state, measurement and interaction boundaries first.

**Controlled MVP → Dynamic Agent Runtime → Richer Human-Agent Interaction**

Future development can progressively increase live Agent-market interaction, adaptive information environments, configurable Agent populations, richer Agent tools, more adaptive feedback and operational scenario configuration.

> Greater Agent autonomy should not come at the cost of state integrity, traceability or reliability.

---

## Quick Start

### Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-marketlens-backend.txt
python -m marketlens.formal_study_startup
```

Backend: `http://localhost:8000`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend: `http://localhost:5173`

---

## Technical Details

<details>
<summary><strong>Open implementation, repository, privacy and attribution details</strong></summary>

### Tech Stack

**Frontend:** React · TypeScript · Vite

**Backend:** Python · FastAPI · SQLite · SQLAlchemy

**AI / Agent:** LLM-driven Agents · BDI-style reasoning · Tool-use · Structured outputs · Bounded context assembly · Embedding support · Retry / fallback

**Evaluation:** pytest · population-sensitivity testing · trajectory validation · protocol audits · session audits

### Repository Structure

```text
MarketLens/
├── frontend/
├── marketlens/
│   ├── agents/
│   ├── episode/
│   ├── experiment/
│   ├── human/
│   ├── information/
│   ├── market/
│   ├── measurement/
│   ├── persistence/
│   ├── source_cues/
│   ├── stimulus/
│   └── validation/
├── tests/
├── docs/
└── requirements-marketlens-backend.txt
```

### Data & Privacy

Public repository contents exclude participant credentials, identifiable participant records, private formal-study databases, local API/provider configuration and private runtime state.

Model context follows a minimum-necessary principle, and participant identity information is not required for model reasoning.

### Research Context

MarketLens was developed as part of an MSc Applied Artificial Intelligence project at the University of Warwick. The formal deployment was used to validate the product's interaction, measurement and reliability model.

### Upstream Attribution

MarketLens uses **TwinMarket** as the underlying LLM-agent financial simulation environment.

TwinMarket was developed by Yuzhe Yang, Yifei Zhang, Minghao Wu, Kaidi Zhang, Yunmiao Zhang, Honghai Yu, Yan Hu and Benyou Wang and was accepted at NeurIPS 2025.

The original upstream README is preserved at:

`docs/upstream/TWINMARKET_ORIGINAL_README.md`

MarketLens adds the human-facing interaction, session/state, information-control, reliability, measurement and evaluation layers described in this repository.

Please refer to the original TwinMarket project and authors when reusing the underlying simulation components.

</details>

---

## License

This repository retains the applicable upstream licensing terms.

See the repository license and upstream attribution for details.
