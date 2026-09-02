# MarketLens

**Human financial judgement and judgement-revision research environment built on TwinMarket**

MarketLens extends the inherited TwinMarket LLM-agent financial-market environment with a controlled human-participant layer for studying how people form and revise financial judgements when exposed to experimentally controlled misinformation and authoritative correction.

> **TwinMarket provides the inherited LLM-agent market environment. MarketLens controls what the participant experiences, records how the participant responds, and prevents participant behaviour from changing the Agent world.**

## Research environment

The formal participant study uses:

- a 15-period participant journey;
- one fixed focal assessment asset: **MEI — Manufacturing Index**;
- a 10-asset participant-visible market;
- repeated formal judgements **J0–J4**;
- controlled misinformation at P1 and authoritative correction at P8;
- participant-only simulated portfolio trading;
- reflective feedback checkpoints after **P4 (F1)**, **P11 (F2)**, and **P15 (Final Session Summary)**;
- a backend-owned experiment state machine and participant-safe information boundary.

Participant decisions and trades never alter the inherited Agent world.

## Current validated release

Release branch:

```text
phase15-participant-ui
```

Validated runtime release HEAD:

```text
92e7a12bfdce502f680238d8becc7e490227b608
```

The release passed the complete deterministic P1–P15 formal participant end-to-end journey, including judgement timing, controlled information exposure, portfolio continuity, F1/F2/Final feedback boundaries, validated fail-closed fallback delivery, debrief gating, participant isolation, and canonical episode byte-identity checks.

**Important evidence boundary:** the deterministic formal-runtime fallback path is validated; this does not claim accepted live-provider output under the final provider preflight contract.

## Formal participant data and analysis

Participant-study data are intentionally kept **local-only** and must not be committed to GitHub.

Recommended local structure:

```text
data/marketlens/human/
├── admin/
│   └── participant_credentials.xlsx
├── formal/
│   ├── participant_runtime.db
│   └── participant_events.db
├── exports/
│   ├── participants.csv
│   ├── judgements_long.csv
│   ├── trades_long.csv
│   ├── portfolio_long.csv
│   ├── feedback_long.csv
│   └── exposures_long.csv
└── preflight/
    └── formal_feedback_provider_v*/
```

Data ownership:

| Data | Authoritative source |
| --- | --- |
| participant/session state | `participant_runtime.db` |
| J0–J4 judgement, confidence, rationale/evidence | `participant_runtime.db` |
| participant trades, holdings, cash, portfolio state | `participant_runtime.db` |
| F1/F2/Final feedback shown to participant | `participant_runtime.db` → `participant_feedback` |
| feedback generation/fallback provenance | `participant_runtime.db` → `participant_feedback_generation` |
| exposure/event provenance | `participant_events.db` → `participant_events` |
| account/password administration | `admin/participant_credentials.xlsx` |
| engineering provider preflight evidence | `preflight/` — **not participant-study observations** |

`participant_events.db` is an append-only exposure/provenance ledger. It is **not** a second source of truth for judgement, trade, or portfolio values.

The intended analysis exports use `participant_id`, `session_id`, `experiment_step`, and `agent_world_date` as the core linking identifiers. Passwords and participant contact information must never be included in analysis exports.

## Inherited foundation

The original TwinMarket project and citation are retained below because MarketLens is built on that technical foundation.

---

# TwinMarket: A Scalable Behavioral and Social Simulation for Financial Markets


[![arXiv](https://img.shields.io/badge/arXiv-2502.01506-b31b1b.svg)](https://arxiv.org/abs/2502.01506)
[![Project Page](https://img.shields.io/badge/Project-Page-blue.svg)](https://freedomintelligence.github.io/TwinMarket/)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Post-0A66C2.svg)](https://www.linkedin.com/feed/update/urn:li:activity:7325176225235173376/)
[![Jiqizhixin](https://img.shields.io/badge/机器之心-Post-0A66C2.svg)](https://mp.weixin.qq.com/s/hxarK4Rxwd4W5mxCMfo_uQ)
[![README](https://img.shields.io/badge/README-English-green.svg)](README.md)
[![README_zh](https://img.shields.io/badge/README-中文-green.svg)](README_zh.md)

 ## 💡 Update
- **09/2025:** TwinMarket was accepted to NeurIPS 2025. See you in San Diego! 🌊
- **04/2025:** TwinMarket won the [Best Paper Award](https://yuzheyang.com/src/img/best_paper.jpg) 🏆 at the [Advances in Financial AI Workshop @ ICLR 2025](https://sites.google.com/view/financialaiiclr25/home).

<div align="center">
  <img src="assets/img/TwinMarket.png" alt="TwinMarket Overview" width="100%" style="max-width: 1000px; margin: 0 auto; display: block;">
</div>

## 📖 Overview

TwinMarket is an innovative stock market simulation system powered by Large Language Models (LLMs). It simulates realistic trading environments through multi-agent collaboration, covering personalized trading strategies, social network interactions, and news/information analysis for an end-to-end market simulation.

## 🎯 Key Features

- **🤖 Intelligent Trading Agents**: LLM-driven, personalized decision-making
- **🌐 Social Network Simulation**: Forum-style interactions and user relationship graphs
- **📊 Multi-dimensional Analytics**: Technical indicators, news, and market sentiment
- **🎲 Behavioral Finance Modeling**: Includes disposition effect, lottery preference, and more
- **⚡ High-performance Concurrency**: Scalable simulation for large user populations
- **📈 Real-time Matching Engine**: Full order matching and execution

## 🚀 Quick Start

```bash
# Configure your API and embedding models
cp config/api_example.yaml config/api.yaml
cp config/embedding_example.yaml config/embedding.yaml

# Run the demo
bash script/run.sh
```

## 📝 Development Guide

### Extend Trading Strategies

Implement new strategies in `trader/trading_agent.py`:

```python
def custom_strategy(self, market_data):
    """Custom trading strategy"""
    # Implement your strategy logic here
    pass
```

### Add New Evaluation Metrics

Add metrics in `trader/utility.py`:

```python
def calculate_custom_metric(trades):
    """Compute custom metric"""
    # Implement metric calculation here
    pass
```

## 📚 Awesome Papers Using TwinMarket

We welcome community contributions. If your paper uses TwinMarket, feel free to open a PR and add it here.

| Title | Code | Paper |
| --- | --- | --- |
| Interpreting Emergent Extreme Events in Multi-Agent Systems | https://github.com/mjl0613ddm/IEEE | https://arxiv.org/abs/2601.20538 |

## 🧾 Citation

```bibtex
@inproceedings{yang2025twinmarket,
  title     = {TwinMarket: A Scalable Behavioral and Social Simulation for Financial Markets},
  author    = {Yuzhe Yang and Yifei Zhang and Minghao Wu and Kaidi Zhang and
               Yunmiao Zhang and Honghai Yu and Yan Hu and Benyou Wang},
  booktitle = {The Thirty-ninth Annual Conference on Neural Information Processing Systems (NeurIPS)},
  series    = {NeurIPS},
  volume    = {39},
  year      = {2025},
  url       = {https://arxiv.org/abs/2502.01506}
}
```

## 📄 License

This project is licensed under the MIT License. See `LICENSE` for details.

## 🌟 Star History

[![Star History Chart](https://api.star-history.com/svg?repos=FreedomIntelligence/TwinMarket&type=date&legend=top-left)](https://www.star-history.com/#FreedomIntelligence/TwinMarket&type=date&legend=top-left)
