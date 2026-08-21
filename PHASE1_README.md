# MarketLens Phase 1 — Minimal Human Backend

## Scope

Phase 1 establishes only the isolated human-participant backend. It does **not** connect to TwinMarket Agents, market reasoning, misinformation/correction stimuli, participant portfolio settlement, or the frontend.

## Long-term project structure

```text
MarketLens/
├── marketlens/                 # MarketLens-owned dissertation code
│   ├── main.py                 # FastAPI entrypoint
│   └── human/                  # Human participant layer
│       ├── schemas.py
│       ├── routers/
│       ├── services/
│       └── stores/
├── tests/
│   └── marketlens/
│       └── human/
│
├── Agent.py                    # inherited TwinMarket core — unchanged
├── simulation.py               # inherited TwinMarket core — unchanged
├── trader/                     # inherited TwinMarket core — unchanged
└── ...
```

Future MarketLens-owned packages will be added beside `human/` as their phases begin, for example `marketlens/agents/` and `marketlens/experiment/`. Inherited TwinMarket core files remain in their original locations unless a separately justified migration is made later.

## Phase 1 API

- `GET /health`
- `POST /session`
- `GET /session/{session_id}`
- `GET /session/{session_id}/state`
- `POST /session/{session_id}/decision`

## Run tests

```bash
python -m pytest tests/marketlens/human -q
```

Expected result:

```text
14 passed
```

## Run backend

```bash
uvicorn marketlens.main:app --reload
```

Then open:

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/docs`

## Experimental boundaries preserved

- Human participant data is stored separately from inherited TwinMarket Agent state.
- Participant sessions are isolated.
- Participant decisions do not mutate TwinMarket.
- Participant-visible state does not expose future experiment information.
- Runtime SQLite files are ignored by Git.

## Temporary Phase 1 conventions

The current backend validates actions as `BUY`, `HOLD`, or `SELL`, and confidence as `0–100`. These are technical placeholders for backend validation, not frozen experimental-instrument decisions.
