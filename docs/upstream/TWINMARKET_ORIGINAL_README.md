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
