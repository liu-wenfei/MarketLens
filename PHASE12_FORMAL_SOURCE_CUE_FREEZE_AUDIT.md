# Phase 12B Formal Source-Cue Freeze Audit

## Purpose

Freeze the already-validated Phase 12A participant-facing source cues without changing the adapter architecture or inherited TwinMarket behavior.

## Reuse boundary

Phase 12B continues to reuse:

- inherited `ForumDB` post `user_id` as the author join key;
- inherited `util.UserDB.get_user_profile(...)["user_type"]` as stable Agent source status;
- Phase 11 `StimulusEngine.participant_payload(...)` as the sole controlled-stimulus visibility/text source;
- Phase 11 `marketlens.stimulus.manifest.sha256_json` for canonical hashing.

No second identity database, timing engine, forum reader, or manifest framework is introduced.

## Frozen participant-facing mappings

Agent source-status display:

- `普通股民 -> Individual Investor`
- `小博主 -> Market Blogger`
- `大V -> Influential Market Commentator`

Controlled misinformation:

- `MISINFO_MEI_OWNERSHIP_001`
- source label: `Market News Report`
- source descriptor: `Market media report`

Controlled correction:

- `CORRECTION_MEI_OWNERSHIP_001`
- source label: `LONGi Green Energy`
- source descriptor: `Official company announcement`

## Formal identity

- cue version: `1.0`
- cue status: `formal_frozen`
- source-cue manifest SHA-256: `67e567351eb77a1edf186239f6205dc43840fbf6e59076813f702fef55b7d5ef`

The manifest hash covers only the exact source-cue display mapping plus cue version/status. Phase 11 stimulus wording remains independently frozen by the Phase 11 material hashes.

## Experimental boundaries

- `user_type` is source status, not truth or reliability.
- dynamic `is_top_user` / graph prominence is not used as credibility.
- the misinformation source cue remains invariant across its visible horizon.
- correction appearance adds the correction cue only; it does not restyle the misinformation.
- no participant judgement, source-rating, confidence, comprehension, trading, checkpoint, or timing parameter is added.
- no Agent prompt, ForumDB row, market state, inherited profile, or protected data file is mutated.

## Versioning rule

Any future change to any frozen English label, controlled source label/descriptor, or cue semantics requires a new Phase 12 cue version and new manifest hash. `formal_frozen` denotes engineering/reproducibility freeze, not external expert, supervisor, ethics, or domain approval.
