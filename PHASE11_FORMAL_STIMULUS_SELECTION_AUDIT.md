# Phase 11B — Formal Stimulus Material Selection Audit

**Status:** CANDIDATE SELECTED FOR REVIEW — NOT FORMAL-FROZEN — NOT FOR PARTICIPANT USE

## 1. Scope

This audit narrows the Phase 11 controlled-stimulus content to one evidence-grounded candidate while preserving the Phase 11A engine contract. It does **not** add participant behavioural parameters, alter Phase 10 timing, modify TwinMarket, or authorize formal participant exposure.

## 2. Candidate selection

Selected candidate:

- target MarketLens stock: `MEI` (Manufacturing Index)
- underlying constituent context: a major solar manufacturer represented in the inherited `stock_profile.csv`
- misinformation direction: positive ownership-link claim
- correction: direct rejection of that ownership link
- candidate file: `data/marketlens/stimuli/stimulus_v1.candidate.json`
- `formal_use_status`: `development`

### Why this candidate was preferred

The historical basis is unusually clean for this project. On 28 February 2022, media reports claimed that a similarly named Hong Kong company associated with LONGi had acquired a 1.8488% stake in Ningxia Baofeng New Energy. LONGi's 1 March 2022 clarification stated that the Hong Kong company was neither a wholly owned nor a controlled subsidiary of LONGi and that LONGi and its subsidiaries had not acquired a stake in the Ningxia company.

This candidate was preferred over the other legacy draft cases because:

1. the underlying misinformation/correction relationship is documented rather than wholly researcher-invented;
2. the authoritative correction predates the frozen 2023 MarketLens simulated world, avoiding future-information leakage;
3. the claim can be expressed as one bounded ownership assertion with a directly matched correction;
4. the Phase 10 visible window's inherited natural-news corpus contains no direct `隆基`, `宝丰`, `多晶硅`, `硅料`, or `光伏` hits, reducing direct collision with the uncontrolled background stream;
5. no forum account, social-proof count, source badge, Agent identity, or market mutation is required for the claim to function.

## 3. Evidence basis

Primary evidence retained outside participant material:

- LONGi Green Energy Technology Co., Ltd., **关于媒体报道的澄清公告**, 1 March 2022
- official page: `https://www.longi.com/cn/bulletin/media-announcement/`

The official clarification states that the media report was untrue, that `Longi Hong Kong Investment Limited` was not a wholly owned or controlled subsidiary of LONGi, and that LONGi and its subsidiaries had not invested in Ningxia Baofeng New Energy.

The participant-facing candidate is an English researcher adaptation, **not a quotation**. Numerical detail is rounded from 1.8488% to approximately 1.85% for readability.

## 4. Candidate participant wording

### Misinformation

**Headline**

> Manufacturing Index solar constituent linked to Ningxia polysilicon investment

**Body**

> A Hong Kong company reported to be associated with a major solar manufacturer in the Manufacturing Index has acquired about a 1.85% stake in a Ningxia polysilicon developer. If the reported ownership link is accurate, the manufacturer would have a new equity connection to upstream polysilicon capacity.

### Authoritative correction

**Headline**

> Correction to reported Ningxia ownership link

**Body**

> The manufacturer clarified that the similarly named Hong Kong investor is neither its wholly owned nor controlled subsidiary, and that neither the manufacturer nor its subsidiaries acquired any stake in the Ningxia company. The reported investment link was therefore incorrect.

## 5. Deliberate wording constraints

The candidate intentionally avoids claims that the minority stake would guarantee supply, lower costs, increase profits, or produce a specific price change. Those consequences are not established by the underlying correction and would unnecessarily strengthen the manipulation through unsupported inference.

The candidate also omits:

- real account handles;
- follower counts / social proof;
- forum post IDs;
- source badges / verification icons;
- Agent identities;
- real-time market-impact claims;
- explicit BUY / SELL recommendations.

Those omissions preserve the frozen boundary that Phase 11 controls **information content**, not participant behaviour or Phase 12 source-cue presentation.

## 6. Timing remains owned by Phase 10

The candidate stores only release events:

- misinformation: `after_J0_before_J1`
- correction: `after_J2_before_J3`

Dates remain derived from protocol v1.1:

- misinformation release: 2023-06-19
- correction release: 2023-06-30

No date is duplicated in the material file.

## 7. Formal-use gate

This candidate is deliberately stamped:

```text
formal_use_status = development
```

Therefore:

```text
load_material(candidate_path, formal=True)
→ FAIL CLOSED
```

Promotion to `formal_frozen` requires a separate bounded freeze step after wording/provenance review. Hashing establishes content identity only; it does not constitute research approval or expert validation.

## 8. Participant behaviour

Phase 11B adds **zero** participant behavioural parameters.

It does not add or change:

- judgement events;
- decision days;
- BUY / SELL / HOLD rules;
- quantity rules;
- confidence questions;
- comprehension checks;
- exposure acknowledgements;
- portfolio mechanics.

## 9. Decision

The MEI ownership-link case is selected as the **single Phase 11 formal-material candidate for review**. It is not yet formal experimental material and must not be tagged as the completed Phase 11 protocol until a later freeze step changes the material to `formal_frozen` and passes formal-mode validation.
