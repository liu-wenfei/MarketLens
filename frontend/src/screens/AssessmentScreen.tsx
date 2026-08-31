import { useMemo, useState } from "react";

import {
  createRequestId,
  submitAssessment,
} from "../api/participantApi";
import { MarketContext } from "../components/MarketContext";
import type {
  DecisionAction,
  ParticipantBackgroundRead,
  ParticipantInformationUpdateRead,
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
    return "Updated Assessment";
  }

  if (view.assessment_mode === "LATER") {
    return "Later Assessment";
  }

  return "Current Assessment";
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
        <span className="eyebrow">Current task</span>
        <h1>{assessmentTitle(view)}</h1>
        <p>
          Record your current view of{" "}
          <strong>{view.assessment_target_stock_id}</strong>.
        </p>
      </div>

      <MarketContext
        view={view}
        background={background}
        informationUpdate={informationUpdate}
      />

      <section className="panel assessment-panel">
        <div className="assessment-question">
          <span className="eyebrow">Your assessment</span>
          <h2>
            What is your current view on{" "}
            {view.assessment_target_stock_id}?
          </h2>
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
          <legend>Information sources considered (optional)</legend>

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
            Brief rationale (optional)
          </label>
          <textarea
            id="rationale"
            rows={4}
            maxLength={5000}
            value={rationale}
            onChange={(event) => setRationale(event.target.value)}
            placeholder="You may briefly explain what informed your current assessment."
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
          {busy ? "Submitting assessment…" : "Submit assessment"}
        </button>
      </section>
    </main>
  );
}
