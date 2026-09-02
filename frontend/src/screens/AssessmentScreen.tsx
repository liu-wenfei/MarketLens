import {
  useCallback,
  useMemo,
  useState,
} from "react";

import {
  createRequestId,
  submitAssessment,
} from "../api/participantApi";
import { MarketContext } from "../components/MarketContext";
import type {
  DecisionAction,
  ParticipantBackgroundRead,
  ParticipantInformationUpdateRead,
  ParticipantMarketOverviewRead,
  ParticipantViewState,
} from "../types/participant";

interface Props {
  view: ParticipantViewState;
  background: ParticipantBackgroundRead | null;
  informationUpdate: ParticipantInformationUpdateRead | null;
  onSubmitted: () => Promise<void>;
}

function assessmentTitle(view: ParticipantViewState): string {
  if (view.assessment_mode === "POST_UPDATE") {
    return "Updated Market Judgement";
  }

  if (view.assessment_mode === "LATER") {
    return "Later Market Judgement";
  }

  return "Current Market Judgement";
}

export function AssessmentScreen({
  view,
  background,
  informationUpdate,
  onSubmitted,
}: Props) {
  const [action, setAction] = useState<DecisionAction | null>(null);
  const [confidence, setConfidence] = useState(50);
  const [evidenceSources, setEvidenceSources] = useState<Set<string>>(
    new Set(),
  );
  const [rationale, setRationale] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [assessmentAssetName, setAssessmentAssetName] =
    useState<string | null>(null);

  const handleMarketOverviewLoaded = useCallback(
    (
      overview: ParticipantMarketOverviewRead,
    ) => {
      const target = overview.assets.find(
        (asset) =>
          asset.stock_id ===
          view.assessment_target_stock_id,
      );

      setAssessmentAssetName(
        target?.display_name ?? null,
      );
    },
    [view.assessment_target_stock_id],
  );

  const assessmentAssetLabel =
    assessmentAssetName === null
      ? view.assessment_target_stock_id
      : `${view.assessment_target_stock_id} — ${assessmentAssetName}`;

  const evidenceOptions = useMemo(() => {
    const options = [
      "Market information",
      "Natural news",
      "Community discussion",
    ];

    if (informationUpdate) {
      options.push("New market information");
    }

    return options;
  }, [informationUpdate]);

  function toggleEvidence(value: string) {
    setEvidenceSources((current) => {
      const next = new Set(current);

      if (next.has(value)) {
        next.delete(value);
      } else {
        next.add(value);
      }

      return next;
    });
  }

  async function handleSubmit() {
    if (!action) {
      return;
    }

    setBusy(true);
    setError(null);

    try {
      await submitAssessment(view.session_id, {
        request_id: createRequestId(),
        action,
        confidence,
        evidence_sources: Array.from(evidenceSources),
        rationale: rationale.trim() || null,
      });

      await onSubmitted();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Unable to submit the assessment.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="screen-shell">
      <div className="screen-title">
        <span className="eyebrow">Think · Market judgement</span>
        <h1>{assessmentTitle(view)}</h1>
        <p>
          Formal market assessments in this study focus on{" "}
          <strong>{assessmentAssetLabel}</strong>. Your judgement is
          recorded separately from any portfolio trade you may choose
          to make.
        </p>

        <div className="participant-progress" aria-label="Session progress">
          <span>
            Market period {view.period_number} of {view.period_count}
          </span>
          <span>{view.market.current_market_date}</span>
          <span>Current task: Market judgement</span>
        </div>
      </div>

      <MarketContext
        view={view}
        background={background}
        informationUpdate={informationUpdate}
        onMarketOverviewLoaded={
          handleMarketOverviewLoaded
        }
      />

      <section className="panel assessment-panel">
        <div className="assessment-question">
          <span className="eyebrow">Assessment asset</span>
          <h2>{assessmentAssetLabel}</h2>
          <p className="interaction-note">
            What is your current BUY, HOLD or SELL judgement for this
            asset? This formal assessment does not execute a trade or
            change your simulated portfolio.
          </p>
        </div>

        <div
          className="decision-options"
          role="group"
          aria-label="Financial assessment"
        >
          {(["BUY", "HOLD", "SELL"] as DecisionAction[]).map(
            (value) => (
              <button
                key={value}
                type="button"
                className={`decision-button ${
                  action === value ? "decision-button--selected" : ""
                }`}
                aria-pressed={action === value}
                onClick={() => setAction(value)}
              >
                {value}
              </button>
            ),
          )}
        </div>

        <div className="form-section">
          <div className="field-heading">
            <label htmlFor="confidence">Confidence</label>
            <strong>{confidence}%</strong>
          </div>

          <input
            id="confidence"
            className="confidence-slider"
            type="range"
            min="0"
            max="100"
            step="1"
            value={confidence}
            onChange={(event) =>
              setConfidence(Number(event.target.value))
            }
          />

          <div className="range-labels">
            <span>0 — very uncertain</span>
            <span>100 — very certain</span>
          </div>
        </div>

        <fieldset className="form-section">
          <legend>Information considered (optional)</legend>

          <div className="evidence-options">
            {evidenceOptions.map((value) => (
              <label className="evidence-option" key={value}>
                <input
                  type="checkbox"
                  checked={evidenceSources.has(value)}
                  onChange={() => toggleEvidence(value)}
                />
                <span>{value}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <div className="form-section">
          <label htmlFor="rationale">
            Brief reasoning (optional)
          </label>
          <textarea
            id="rationale"
            rows={4}
            maxLength={5000}
            value={rationale}
            onChange={(event) => setRationale(event.target.value)}
            placeholder="You may briefly note what informed your current judgement."
          />
        </div>

        {error && <div className="error-banner">{error}</div>}

        <button
          className="primary-button"
          type="button"
          disabled={
            busy ||
            !action ||
            !view.allowed_actions.submit_assessment
          }
          onClick={() => void handleSubmit()}
        >
          {busy ? "Recording judgement…" : "Record Market Judgement"}
        </button>
      </section>
    </main>
  );
}
