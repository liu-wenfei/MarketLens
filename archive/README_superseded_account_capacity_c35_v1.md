# Superseded Account-Capacity Diagnostic — c35

**Status:** SUPERSEDED DEVELOPMENT DIAGNOSTIC
**Not formal participant-account evidence.**

This archive preserves the earlier MarketLens account-capacity analysis that
assumed a participant account with non-zero initial risky holdings.

Historical assumptions included:
- approximately 35% initial cash;
- approximately 65% initial risky holdings;
- a 13% position cap;
- a 10 bps transaction cost;
- analysis developed for an earlier protocol rather than the final 15-Period
  human-participant protocol.

These assumptions were superseded after the final participant design was
clarified: human participants start with a cash-only account and no initial
holdings.

The formal participant-account configuration is:

- initial cash: 10,000 simulated units;
- initial holdings: none;
- transaction cost: 0 bps;
- position cap: none;
- whole-unit settlement: enabled;
- short selling: disabled;
- leverage: disabled.

Formal implementation commit:
ae2e1ec249e1c1fa372289c6bf2aa10d6ac36234

Formal validation-evidence commit:
9d8cc09affec7176641910632ea0d1433793eea0

The archived c35 analysis may be retained as development-history material or
appendix provenance, but must not be described as the implemented formal
participant account.

Archive SHA-256:
41360c5e2fa6d89b37526b68126064fc93b0fbc64231fefc416326eb9800e8ef
