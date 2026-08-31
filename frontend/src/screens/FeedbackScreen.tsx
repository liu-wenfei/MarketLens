import { useEffect, useState } from "react";

import {
  continueCurrentFeedback,
  createRequestId,
  getCurrentFeedback,
  getDecisionJourney,
} from "../api/participantApi";
import type {
  ParticipantDecisionJourneyRead,
  ParticipantFeedbackRead,
  ParticipantViewState,
} from "../types/participant";

interface Props {
  view: ParticipantViewState;
  onContinued: () => Promise<void>;
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-GB", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

export function FeedbackScreen({
  view,
  onContinued,
}: Props) {
  const [feedback, setFeedback] =
    useState<ParticipantFeedbackRead | null>(null);
  const [journey, setJourney] =
    useState<ParticipantDecisionJourneyRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function load() {
      setLoading(true);
      setError(null);

      try {
        const [feedbackResult, journeyResult] = await Promise.all([
          getCurrentFeedback(view.session_id),
          getDecisionJourney(view.session_id),
        ]);

        if (active) {
          setFeedback(feedbackResult);
          setJourney(journeyResult);
        }
      } catch (caught) {
        if (active) {
          setError(
            caught instanceof Error
              ? caught.message
              : "Unable to load decision feedback.",
          );
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void load();

    return () => {
      active = false;
    };
  }, [view.session_id]);

  async function handleContinue() {
    setBusy(true);
    setError(null);

    try {
      await continueCurrentFeedback(
        view.session_id,
        createRequestId(),
      );
      await onContinued();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Unable to continue from feedback.",
      );
    } finally {
      setBusy(false);
    }
  }

  const finalSummary =
    feedback?.feedback_kind === "final_session_summary";

  const finalPortfolioValue =
    journey && journey.periods.length > 0
      ? journey.periods[journey.periods.length - 1].portfolio_end
          .portfolio_value
      : null;

  return (
    <main className="screen-shell feedback-shell">
      <div className="screen-title">
        <span className="eyebrow">
          {finalSummary ? "Session reflection" : "Decision reflection"}
        </span>
        <h1>
          {finalSummary
            ? "Your MarketLens Session Summary"
            : "Decision Feedback"}
        </h1>
        <p>
          This reflection is based on your recorded decision journey.
        </p>
      </div>

      {loading && (
        <section className="panel">
          <p className="empty-copy">Loading feedback…</p>
        </section>
      )}

      {error && <div className="error-banner">{error}</div>}

      {feedback && (
        <section className="panel reflection-panel">
          <span className="eyebrow">Your reflection</span>
          <p className="reflection-copy">{feedback.reflection}</p>
        </section>
      )}

      {journey && (
        <section className="panel journey-panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Decision journey</span>
              <h2>Market periods completed</h2>
            </div>
            <span className="count-badge">
              {journey.periods.length}
            </span>
          </div>

          {finalSummary && finalPortfolioValue !== null && (
            <div className="final-summary-metrics">
              <div>
                <span>Starting portfolio value</span>
                <strong>
                  {formatNumber(journey.initial_portfolio_value)}
                </strong>
              </div>
              <div>
                <span>Current portfolio value</span>
                <strong>
                  {formatNumber(finalPortfolioValue)}
                </strong>
              </div>
            </div>
          )}

          <div className="journey-list">
            {journey.periods.map((period) => (
              <article
                className="journey-row"
                key={period.period_number}
              >
                <div className="journey-row__period">
                  <strong>Period {period.period_number}</strong>
                  <span>{period.agent_world_date}</span>
                </div>

                <div className="journey-row__judgements">
                  {period.judgements.length > 0 ? (
                    period.judgements.map((judgement) => (
                      <span
                        className="judgement-chip"
                        key={`${period.period_number}-${judgement.sequence_within_period}`}
                      >
                        {judgement.action} ·{" "}
                        {formatNumber(judgement.confidence)}%
                      </span>
                    ))
                  ) : (
                    <span className="small-meta">
                      No formal assessment
                    </span>
                  )}
                </div>

                <div className="journey-row__behaviour">
                  <span>Behaviour</span>
                  <strong>
                    {period.behaviour_summary
                      .replaceAll("_", " ")
                      .toLowerCase()}
                  </strong>
                </div>

                {finalSummary && (
                  <div className="journey-row__portfolio">
                    <span>Portfolio value</span>
                    <strong>
                      {formatNumber(
                        period.portfolio_end.portfolio_value,
                      )}
                    </strong>
                  </div>
                )}
              </article>
            ))}
          </div>
        </section>
      )}

      {feedback && (
        <section className="panel action-panel">
          <p>
            Continue when you have finished reading this reflection.
          </p>

          <button
            type="button"
            className="primary-button"
            disabled={busy}
            onClick={() => void handleContinue()}
          >
            {busy
              ? "Continuing…"
              : finalSummary
                ? "Continue to debrief"
                : "Continue"}
          </button>
        </section>
      )}
    </main>
  );
}
