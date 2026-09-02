# MarketLens

**基于 TwinMarket 构建的人类金融判断与判断修正研究环境**

MarketLens 在继承的 TwinMarket LLM-Agent 金融市场环境之上增加了受控的人类参与者实验层，用于研究参与者在接触实验控制的 misinformation 与 authoritative correction 后，如何形成并修正金融判断。

> **TwinMarket 提供继承的 LLM-Agent 市场环境；MarketLens 控制参与者看到什么、记录参与者如何反应，并保证参与者行为不会改变 Agent world。**

## 实验环境

正式参与者实验包括：

- 15 个 Market Period；
- 一个固定正式判断对象：**MEI — Manufacturing Index**；
- 10 个参与者可见、可交易资产；
- J0–J4 五次正式判断；
- P1 的 controlled misinformation 与 P8 的 authoritative correction；
- 仅影响参与者自身的模拟 Portfolio；
- P4 后 **F1**、P11 后 **F2**、P15 后 **Final Session Summary**；
- 由后端唯一控制的实验状态机与 participant-safe information boundary。

参与者判断和交易永远不会改变继承的 Agent world。

## 当前正式验证版本

Release branch：

```text
phase15-participant-ui
```

Validated runtime release HEAD：

```text
92e7a12bfdce502f680238d8becc7e490227b608
```

该版本已通过完整 deterministic P1–P15 formal participant E2E，包括判断时序、受控信息暴露、Portfolio continuity、F1/F2/Final Feedback 边界、validated fail-closed fallback、Debrief gating、参与者隔离以及 canonical episode byte identity。

**证据边界：**已经验证 deterministic formal-runtime fallback path；不能据此声称最终 provider preflight contract 下的 live-provider output 已正式通过 acceptance。

## 正式参与者数据与分析目录

参与者正式实验数据必须保持 **local-only**，不得提交到 GitHub。

推荐本地结构：

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

数据 source of truth：

| 数据 | Authoritative source |
| --- | --- |
| participant/session state | `participant_runtime.db` |
| J0–J4 judgement、confidence、rationale/evidence | `participant_runtime.db` |
| participant trades、holdings、cash、portfolio | `participant_runtime.db` |
| 参与者实际看到的 F1/F2/Final Feedback | `participant_runtime.db` → `participant_feedback` |
| Feedback generation/fallback provenance | `participant_runtime.db` → `participant_feedback_generation` |
| exposure/event provenance | `participant_events.db` → `participant_events` |
| 账号/密码行政管理 | `admin/participant_credentials.xlsx` |
| provider preflight 工程证据 | `preflight/` — **不是 participant-study observations** |

`participant_events.db` 是 append-only exposure/provenance ledger，**不是** judgement、trade 或 portfolio 的第二份 source of truth。

后续 analysis-ready exports 主要通过 `participant_id`、`session_id`、`experiment_step` 和 `agent_world_date` 关联。密码和参与者联系方式不得进入分析导出文件。

## 继承的 TwinMarket 基础

下面保留原 TwinMarket 项目信息与引用，因为 MarketLens 建立在该技术基础之上。

---

# TwinMarket - A股市场模拟系统（1.0版本）

<p align="center">[ <a href="README.md">English</a> | <a href="README_zh.md">中文</a> ]</p>

<div align="center">
  <img src="assets/img/TwinMarket.png" alt="TwinMarket Overview" width="100%" style="max-width: 1000px; margin: 0 auto; display: block;">
</div>

## 📖 项目简介

TwinMarket 是一个创新的股票交易模拟系统，通过集成大语言模型（LLM）技术，模拟真实的股票市场交易环境。系统通过多智能体协作，实现了包括个性化交易策略、社交网络互动、新闻信息分析等在内的全方位市场模拟。

### 🎯 核心特性

- **🤖 智能交易代理**：基于 LLM 的个性化交易决策系统
- **🌐 社交网络模拟**：完整的论坛互动和用户关系网络
- **📊 多维度分析**：整合技术指标、新闻信息、市场情绪等多种因素
- **🎲 行为金融建模**：考虑处置效应、彩票偏好等行为金融因素
- **⚡ 高性能并发**：支持大规模用户并发交易模拟
- **📈 实时撮合引擎**：完整的订单撮合和交易执行系统

## 🚀 快速开始

```bash
# 自行配置 API 与 embedding 模型：
cp config/api_example.yaml config/api.yaml
cp config/embedding_example.yaml config/embedding.yaml

# 运行样例
bash script/run.sh
```

## 📝 开发指南

### 扩展交易策略

在 `trader/trading_agent.py` 中实现新的交易策略：

```python
def custom_strategy(self, market_data):
    """自定义交易策略"""
    # 实现你的策略逻辑
    pass
```

### 添加新的评估指标

在 `trader/utility.py` 中添加评估函数：

```python
def calculate_custom_metric(trades):
    """计算自定义指标"""
    # 实现指标计算
    pass
```

## 📚 使用 TwinMarket 的优秀论文

欢迎社区贡献。如果你的论文使用了 TwinMarket，欢迎提交 PR 添加到这里。

| 标题 | 代码 | 论文 |
| --- | --- | --- |
| Interpreting Emergent Extreme Events in Multi-Agent Systems | https://github.com/mjl0613ddm/IEEE | https://arxiv.org/abs/2601.20538 |

## 🧾 引用

```bibtex
@inproceedings{yang2025twinmarket,
      title={TwinMarket: A Scalable Behavioral and Social Simulation for Financial Markets},
      author={Yuzhe Yang and Yifei Zhang and Minghao Wu and Kaidi Zhang and
              Yunmiao Zhang and Honghai Yu and Yan Hu and Benyou Wang},
      booktitle={The Thirty-ninth Annual Conference on Neural Information Processing Systems (NeurIPS)},
      series={NeurIPS},
      volume={39},
      year={2025},
      url={https://arxiv.org/abs/2502.01506},
}
```

## 📄 许可证

本项目采用 MIT License，详见 `LICENSE`。
