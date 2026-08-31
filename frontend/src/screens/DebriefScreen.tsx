import { useState } from "react";

import { completeDebrief } from "../api/participantApi";

interface Props {
  sessionId: string;
  onCompleted: () => Promise<void>;
}

export function DebriefScreen({
  sessionId,
  onCompleted,
}: Props) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleFinish() {
    setSubmitting(true);
    setError(null);

    try {
      await completeDebrief(sessionId);
      await onCompleted();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Unable to complete the study.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="screen-shell screen-shell--focused">
      <section className="task-card debrief-card">
        <span className="eyebrow">Study debrief</span>
        <h1>Study Debrief</h1>

        <p className="lead-copy">
          Your MarketLens session has reached the debrief stage.
        </p>

        <p>
          Please review the formal study debrief information provided
          by the research team before finishing this session.
        </p>

        <div className="debrief-notice">
          The study server controls completion of this session.
        </div>

        {error && (
          <div className="error-banner">
            {error}
          </div>
        )}

        <button
          className="primary-button"
          type="button"
          disabled={submitting}
          onClick={() => void handleFinish()}
        >
          {submitting ? "Finishing…" : "Finish Study"}
        </button>
      </section>
    </main>
  );
}
