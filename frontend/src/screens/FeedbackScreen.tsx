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

function metricGroup(
  statistics: Record<string, unknown>,
  name: string,
): Record<string, unknown> | null {
  const value = statistics[name];

  if (
    value === null ||
    typeof value !== "object" ||
    Array.isArray(value)
  ) {
    return null;
  }

  return value as Record<string, unknown>;
}

function numberMetric(
  group: Record<string, unknown> | null,
  name: string,
): number | null {
  const value = group?.[name];
  return typeof value === "number" && Number.isFinite(value)
    ? value
    : null;
}

function textMetric(
  group: Record<string, unknown> | null,
  name: string,
): string | null {
  const value = group?.[name];
  return typeof value === "string" ? value : null;
}

function availableNumberMetric(
  group: Record<string, unknown> | null,
  name: string,
): number | null {
  const raw = group?.[name];

  if (
    raw === null ||
    typeof raw !== "object" ||
    Array.isArray(raw)
  ) {
    return null;
  }

  const wrapper = raw as Record<string, unknown>;

  if (wrapper.available !== true) {
    return null;
  }

  const value = wrapper.value;

  return typeof value === "number" && Number.isFinite(value)
    ? value
    : null;
}

function objectArrayMetric(
  group: Record<string, unknown> | null,
  name: string,
): Record<string, unknown>[] {
  const raw = group?.[name];

  if (!Array.isArray(raw)) {
    return [];
  }

  return raw.filter(
    (item): item is Record<string, unknown> =>
      item !== null &&
      typeof item === "object" &&
      !Array.isArray(item),
  );
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
        const feedbackResult = await getCurrentFeedback(
          view.session_id,
        );

        let journeyResult:
          | ParticipantDecisionJourneyRead
          | null = null;

        if (feedbackResult.reflection_stage === "final") {
          journeyResult = await getDecisionJourney(
            view.session_id,
          );
        }

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

  const reflectionStage = feedback?.reflection_stage ?? null;
  const earlyReflection = reflectionStage === "early";
  const midSessionReflection = reflectionStage === "mid_session";
  const finalSummary = reflectionStage === "final";

  const feedbackEyebrow = finalSummary
    ? "Session reflection"
    : midSessionReflection
      ? "Mid-session reflection"
      : earlyReflection
        ? "Early reflection"
        : "Decision reflection";

  const feedbackTitle = finalSummary
    ? "Your MarketLens Session Summary"
    : midSessionReflection
      ? "How Your Decision Process Has Changed"
      : "Early Decision Reflection";

  const feedbackDescription = finalSummary
    ? "This reflection reviews your recorded decision journey across the full session."
    : midSessionReflection
      ? "This reflection focuses on changes between your earlier and more recent decision process."
      : "This reflection focuses on patterns beginning to appear in your recorded decision process.";

  const finalPortfolioValue =
    journey && journey.periods.length > 0
      ? journey.periods[journey.periods.length - 1].portfolio_end
          .portfolio_value
      : null;

  const statistics = feedback?.statistics ?? {};
  const judgementMetrics = metricGroup(
    statistics,
    "judgement_metrics",
  );
  const confidenceMetrics = metricGroup(
    statistics,
    "confidence_metrics",
  );
  const tradingMetrics = metricGroup(
    statistics,
    "trading_metrics",
  );
  const portfolioMetrics = metricGroup(
    statistics,
    "portfolio_metrics",
  );
  const evidenceMetrics = metricGroup(
    statistics,
    "reported_evidence_metrics",
  );

  const finalOnlyMetrics = metricGroup(
    statistics,
    "final_only_metrics",
  );
  const turnoverMetrics = metricGroup(
    finalOnlyMetrics ?? {},
    "executed_turnover",
  );
  const drawdownMetrics = metricGroup(
    finalOnlyMetrics ?? {},
    "maximum_drawdown",
  );
  const constructionMetrics = metricGroup(
    finalOnlyMetrics ?? {},
    "portfolio_construction",
  );
  const equityCurve = objectArrayMetric(
    finalOnlyMetrics,
    "equity_curve",
  );

  const firstAssessment = textMetric(
    judgementMetrics,
    "first_assessment",
  );
  const latestAssessment = textMetric(
    judgementMetrics,
    "latest_assessment",
  );
  const revisionCount = numberMetric(
    judgementMetrics,
    "revision_count",
  );

  return (
    <main className="screen-shell feedback-shell">
      <div className="screen-title">
        <span className="eyebrow">{feedbackEyebrow}</span>
        <h1>{feedbackTitle}</h1>
        <p>{feedbackDescription}</p>
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

      {feedback && (
        <section className="panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Decision pattern</span>
              <h2>Recorded assessment summary</h2>
            </div>
          </div>

          <div className="final-summary-metrics">
            <div>
              <span>First judgement</span>
              <strong>{firstAssessment ?? "Unavailable"}</strong>
            </div>
            <div>
              <span>Latest judgement</span>
              <strong>{latestAssessment ?? "Unavailable"}</strong>
            </div>
            <div>
              <span>Revisions</span>
              <strong>
                {revisionCount === null ? "Unavailable" : revisionCount}
              </strong>
            </div>
            <div>
              <span>Latest confidence</span>
              <strong>
                {numberMetric(confidenceMetrics, "latest") === null
                  ? "Unavailable"
                  : `${formatNumber(
                      numberMetric(confidenceMetrics, "latest") as number,
                    )}%`}
              </strong>
            </div>
          </div>
        </section>
      )}

      {feedback && (
        <section className="panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Recorded activity</span>
              <h2>Trading activity in this feedback window</h2>
            </div>
          </div>

          <div className="final-summary-metrics">
            <div>
              <span>Transactions</span>
              <strong>
                {numberMetric(tradingMetrics, "transaction_count") ?? 0}
              </strong>
            </div>
            <div>
              <span>Active trading periods</span>
              <strong>
                {numberMetric(tradingMetrics, "trade_periods") ?? 0}
              </strong>
            </div>
            <div>
              <span>No-trade periods</span>
              <strong>
                {numberMetric(tradingMetrics, "no_trade_periods") ?? 0}
              </strong>
            </div>
            {(midSessionReflection || finalSummary) && (
              <div>
                <span>Buy / sell actions</span>
                <strong>
                  {numberMetric(tradingMetrics, "buy_actions") ?? 0} /{" "}
                  {numberMetric(tradingMetrics, "sell_actions") ?? 0}
                </strong>
              </div>
            )}
            {finalSummary &&
              numberMetric(
                tradingMetrics,
                "gross_executed_notional",
              ) !== null && (
                <div>
                  <span>Gross executed notional</span>
                  <strong>
                    {formatNumber(
                      numberMetric(
                        tradingMetrics,
                        "gross_executed_notional",
                      ) as number,
                    )}
                  </strong>
                </div>
              )}

            {finalSummary && turnoverMetrics && (
              <>
                <div>
                  <span>Total executed turnover</span>
                  <strong>
                    {numberMetric(
                      turnoverMetrics,
                      "total_turnover_pct",
                    ) === null
                      ? "Unavailable"
                      : `${formatNumber(
                          numberMetric(
                            turnoverMetrics,
                            "total_turnover_pct",
                          ) as number,
                        )}%`}
                  </strong>
                </div>

                <div>
                  <span>Average daily turnover</span>
                  <strong>
                    {numberMetric(
                      turnoverMetrics,
                      "average_daily_turnover_pct",
                    ) === null
                      ? "Unavailable"
                      : `${formatNumber(
                          numberMetric(
                            turnoverMetrics,
                            "average_daily_turnover_pct",
                          ) as number,
                        )}%`}
                  </strong>
                </div>
              </>
            )}
          </div>
        </section>
      )}

      {feedback && (midSessionReflection || finalSummary) && (
        <section className="panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Confidence pattern</span>
              <h2>Confidence across recorded assessments</h2>
            </div>
          </div>

          <div className="final-summary-metrics">
            <div>
              <span>Mean confidence</span>
              <strong>
                {numberMetric(confidenceMetrics, "mean") === null
                  ? "Unavailable"
                  : `${formatNumber(
                      numberMetric(confidenceMetrics, "mean") as number,
                    )}%`}
              </strong>
            </div>
            <div>
              <span>Minimum confidence</span>
              <strong>
                {numberMetric(confidenceMetrics, "minimum") === null
                  ? "Unavailable"
                  : `${formatNumber(
                      numberMetric(confidenceMetrics, "minimum") as number,
                    )}%`}
              </strong>
            </div>
            <div>
              <span>Maximum confidence</span>
              <strong>
                {numberMetric(confidenceMetrics, "maximum") === null
                  ? "Unavailable"
                  : `${formatNumber(
                      numberMetric(confidenceMetrics, "maximum") as number,
                    )}%`}
              </strong>
            </div>
          </div>
        </section>
      )}

      {feedback && (midSessionReflection || finalSummary) && evidenceMetrics && (
        <section className="panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Participant-reported evidence</span>
              <h2>Evidence selections recorded with your assessments</h2>
            </div>
          </div>

          <p className="small-meta">
            These counts describe evidence sources you reported selecting.
            They do not infer what you read, believed, or considered correct.
          </p>

          <div className="final-summary-metrics">
            <div>
              <span>Total selections</span>
              <strong>
                {numberMetric(evidenceMetrics, "total_selections") ?? 0}
              </strong>
            </div>
            <div>
              <span>Assessments with evidence</span>
              <strong>
                {numberMetric(
                  evidenceMetrics,
                  "assessments_with_evidence",
                ) ?? 0}
              </strong>
            </div>
            <div>
              <span>Unique reported sources</span>
              <strong>
                {numberMetric(
                  evidenceMetrics,
                  "unique_reported_sources",
                ) ?? 0}
              </strong>
            </div>
            <div>
              <span>Repeated selections</span>
              <strong>
                {numberMetric(evidenceMetrics, "repeated_selections") ?? 0}
              </strong>
            </div>
            <div>
              <span>Evidence-set changes</span>
              <strong>
                {numberMetric(evidenceMetrics, "evidence_set_changes") ?? 0}
              </strong>
            </div>
          </div>
        </section>
      )}

      {feedback && (midSessionReflection || finalSummary) && portfolioMetrics && (
        <section className="panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Portfolio movement</span>
              <h2>Portfolio value across this feedback window</h2>
            </div>
          </div>

          <div className="final-summary-metrics">
            <div>
              <span>Starting value</span>
              <strong>
                {numberMetric(portfolioMetrics, "starting_value") === null
                  ? "Unavailable"
                  : formatNumber(
                      numberMetric(
                        portfolioMetrics,
                        "starting_value",
                      ) as number,
                    )}
              </strong>
            </div>
            <div>
              <span>Ending value</span>
              <strong>
                {numberMetric(portfolioMetrics, "ending_value") === null
                  ? "Unavailable"
                  : formatNumber(
                      numberMetric(
                        portfolioMetrics,
                        "ending_value",
                      ) as number,
                    )}
              </strong>
            </div>
            <div>
              <span>Absolute change</span>
              <strong>
                {numberMetric(portfolioMetrics, "absolute_change") === null
                  ? "Unavailable"
                  : formatNumber(
                      numberMetric(
                        portfolioMetrics,
                        "absolute_change",
                      ) as number,
                    )}
              </strong>
            </div>
            <div>
              <span>Change</span>
              <strong>
                {numberMetric(portfolioMetrics, "change_pct") === null
                  ? "Unavailable"
                  : `${formatNumber(
                      numberMetric(portfolioMetrics, "change_pct") as number,
                    )}%`}
              </strong>
            </div>

            {finalSummary && (
              <div>
                <span>Maximum drawdown</span>
                <strong>
                  {numberMetric(
                    drawdownMetrics,
                    "value_pct",
                  ) === null
                    ? "Unavailable"
                    : `${formatNumber(
                        numberMetric(
                          drawdownMetrics,
                          "value_pct",
                        ) as number,
                      )}%`}
                </strong>
              </div>
            )}
          </div>

          {finalSummary &&
            textMetric(drawdownMetrics, "peak_date") &&
            textMetric(drawdownMetrics, "trough_date") && (
              <p className="small-meta">
                Maximum drawdown ran from{" "}
                {textMetric(drawdownMetrics, "peak_date")} to{" "}
                {textMetric(drawdownMetrics, "trough_date")}.
              </p>
            )}
        </section>
      )}

      {feedback &&
        finalSummary &&
        constructionMetrics && (
          <section className="panel">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">
                  FINAL portfolio construction
                </span>
                <h2>How your final portfolio was allocated</h2>
              </div>
            </div>

            <p className="small-meta">
              Concentration measures use risky holdings only; cash is
              excluded from risky-asset HHI and effective holdings.
            </p>

            <div className="final-summary-metrics">
              <div>
                <span>Cash weight</span>
                <strong>
                  {availableNumberMetric(
                    constructionMetrics,
                    "cash_weight_pct",
                  ) === null
                    ? "Unavailable"
                    : `${formatNumber(
                        availableNumberMetric(
                          constructionMetrics,
                          "cash_weight_pct",
                        ) as number,
                      )}%`}
                </strong>
              </div>

              <div>
                <span>Risky holdings</span>
                <strong>
                  {numberMetric(
                    constructionMetrics,
                    "risky_holding_count",
                  ) ?? "Unavailable"}
                </strong>
              </div>

              <div>
                <span>Largest risky holding weight</span>
                <strong>
                  {availableNumberMetric(
                    constructionMetrics,
                    "largest_risky_holding_weight_pct",
                  ) === null
                    ? "Unavailable"
                    : `${formatNumber(
                        availableNumberMetric(
                          constructionMetrics,
                          "largest_risky_holding_weight_pct",
                        ) as number,
                      )}%`}
                </strong>
              </div>

              <div>
                <span>Risky-asset HHI</span>
                <strong>
                  {availableNumberMetric(
                    constructionMetrics,
                    "risky_hhi",
                  ) === null
                    ? "Unavailable"
                    : formatNumber(
                        availableNumberMetric(
                          constructionMetrics,
                          "risky_hhi",
                        ) as number,
                      )}
                </strong>
              </div>

              <div>
                <span>Effective risky holdings</span>
                <strong>
                  {availableNumberMetric(
                    constructionMetrics,
                    "effective_risky_holdings",
                  ) === null
                    ? "Unavailable"
                    : formatNumber(
                        availableNumberMetric(
                          constructionMetrics,
                          "effective_risky_holdings",
                        ) as number,
                      )}
                </strong>
              </div>
            </div>
          </section>
        )}

      {feedback && finalSummary && equityCurve.length > 0 && (
        <section className="panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Portfolio value path</span>
              <h2>Equity curve across P1–P15</h2>
            </div>
          </div>

          <p className="small-meta">
            Each point is the authoritative end-of-period participant
            portfolio value for that period.
          </p>

          <div className="final-summary-metrics">
            {equityCurve.map((point, index) => {
              const date = textMetric(point, "date");
              const value = numberMetric(
                point,
                "portfolio_value",
              );

              return (
                <div key={`${date ?? "period"}-${index}`}>
                  <span>
                    P{index + 1}
                    {date ? ` · ${date}` : ""}
                  </span>
                  <strong>
                    {value === null
                      ? "Unavailable"
                      : formatNumber(value)}
                  </strong>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {finalSummary && journey && (
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
