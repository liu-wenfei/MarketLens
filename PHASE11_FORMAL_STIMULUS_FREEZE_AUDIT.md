# Phase 11C — Formal Stimulus Material Freeze Audit

## Status

**Selected formal material:** MEI / LONGi–Ningxia Baofeng ownership-link claim
**Protocol:** Phase 10 v1.1
**Material version:** 1.0
**Formal status:** `formal_frozen`
**Participant behavioural parameters added:** **0**

This document freezes the exact controlled misinformation/correction wording used by the Phase 11 participant-only stimulus engine. It does **not** change the Phase 10 timing protocol, participant decision rules, Agent-world dynamics, or source-cue presentation.

## 1. Why this claim was selected

The selected claim is evidence-grounded rather than researcher-invented. On 28 February 2022, media reporting described `Longi Hong Kong Investment Limited` as a LONGi-linked/subsidiary company and reported that it held 1.8488% of Ningxia Baofeng New Energy Technology Co., Ltd. On 1 March 2022, LONGi issued a clarification stating that the Hong Kong company was neither its wholly owned nor controlled subsidiary and that LONGi and its subsidiaries had not acquired any stake in Ningxia Baofeng New Energy.

Primary provenance:
- LONGi Green Energy Technology Co., Ltd., **Clarification Announcement on Media Reports**, 1 March 2022: https://www.longi.com/cn/bulletin/media-announcement/

Secondary contemporaneous confirmation:
- China Securities Journal / China Securities Network, 1 March 2022: https://cs.com.cn/ssgs/gsxw/202203/t20220301_6246113.html

The clarification predates the MarketLens simulated-world start date (2023-06-15), so the correction is not future information relative to the simulated market world.

## 2. Target-stock compatibility

The inherited `data/stock_profile.csv` defines `MEI` as the Manufacturing Index and includes LONGi Green Energy (SH601012) as a constituent. The controlled claim therefore has a direct, pre-existing mapping to the participant's MEI decision target without modifying TwinMarket data.

No weight, expected return, price target, profit effect, or recommendation is inserted into the stimulus. The stimulus does not tell the participant how MEI should move.

## 3. Exact frozen misinformation

**ID:** `MISINFO_MEI_OWNERSHIP_001`

**Headline**

> Manufacturing Index constituent LONGi takes 1.85% stake in Ningxia Baofeng New Energy

**Body**

> LONGi Hong Kong Investment Limited, a subsidiary of LONGi Green Energy, has acquired a 1.8488% stake in Ningxia Baofeng New Energy Technology Co., Ltd.

The false proposition is deliberately narrow:

`Longi Hong Kong Investment Limited is a LONGi subsidiary` + `therefore the reported 1.8488% holding represents a LONGi investment`.

The formal wording removes the Phase 11B candidate's extra conditional inference about upstream capacity. It contains no BUY/SELL recommendation, price direction, supply guarantee, cost implication, earnings implication, or portfolio instruction.

## 4. Exact frozen authoritative correction

**ID:** `CORRECTION_MEI_OWNERSHIP_001`

**Headline**

> Correction: reported LONGi stake in Ningxia Baofeng was inaccurate

**Body**

> LONGi Hong Kong Investment Limited is neither a wholly owned nor controlled subsidiary of LONGi Green Energy. LONGi Green Energy and its subsidiaries did not acquire any stake in Ningxia Baofeng New Energy Technology Co., Ltd.

The correction targets exactly the misinformation stimulus via `corrects_stimulus_id` and negates both components of the same ownership/investment claim. It does not introduce a new financial forecast.

## 5. Source-cue separation

Phase 11 freezes **content**, not source presentation. The formal text contains no source logo, verification badge, account handle, social-proof count, authority score, or UI styling. Those presentation cues remain outside Phase 11.

The internal schema still classifies the second item as `authoritative_correction`; participant-facing source-cue rendering is handled later by the dedicated source-cue layer.

## 6. Timing and persistence remain inherited from Phase 10

The formal material contains no release dates. It stores only the already-frozen release events:

- misinformation: `after_J0_before_J1`
- correction: `after_J2_before_J3`

The Phase 11 engine derives their dates from Phase 10 v1.1:

- misinformation release: 2023-06-19
- correction release: 2023-06-30

The misinformation remains visible after correction; the correction is added rather than replacing/deleting the historical misinformation item.

## 7. Background-news collision gate

The Phase 11C zero-LLM preflight scans inherited `data/sorted_impact_news.pkl` across the participant-visible formal window (2023-06-19 through 2023-07-11) for direct lexical collisions with:

`隆基`, `LONGi`, `601012`, `宝丰`, `多晶硅`, `polysilicon`.

The formal freeze requires zero direct collisions for this declared term set. This is a narrow collision guard, not a claim that the wider natural information environment is semantically unrelated.

## 8. Frozen hashes

- misinformation SHA-256: `7846c55c7b5ccbcb97ff28ec8d8c52a1b51336197805b7fec4aa4d3e226403b6`
- correction SHA-256: `fd042b4cbe194ef544bd162c7605da75678c32d654c6ae722867c2debd3cf269`
- material manifest SHA-256: `e65fe566a58af44f0738b14fff160a09dfc42f34d73455accb92aae2cdadef9a`

Any wording, ID, release-event, status, version, target-stock, or correction-link change invalidates the relevant hash/manifest and must be treated as a new material version.

## 9. Explicit non-decisions

Phase 11C does **not** add or modify:

- participant decision days;
- BUY/SELL/HOLD rules;
- quantity rules;
- judgement checkpoints;
- confidence/comprehension questions;
- participant portfolio mechanics;
- Agent activation/reasoning;
- ForumDB/belief propagation;
- matching or price formation;
- inherited background news;
- source-cue UI.

## 10. Meaning of `formal_frozen`

`formal_frozen` is an engineering/reproducibility status: it means the exact material text, IDs, target mapping, timing links, and hashes are frozen for the declared protocol version. It does **not** by itself assert independent ethics, supervisor, or domain-expert approval. If such review requires wording changes, the material must receive a new version and new hashes before participant use.

## 11. Freeze criterion

Phase 11 is eligible for final freeze only after:

1. formal material loads with `formal=True`;
2. exact content/manifest hashes match the constants above;
3. Phase 10-derived timing/persistence truth table passes;
4. MEI→LONGi inherited target mapping passes;
5. declared background-news direct-collision count is zero;
6. TwinMarket protected sources/data remain unchanged;
7. narrow and full regressions pass;
8. clean-HEAD zero-LLM formal-material preflight reproduces the same result.
