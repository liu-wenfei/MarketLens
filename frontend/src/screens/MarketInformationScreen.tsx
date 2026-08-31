import { useState } from "react";

import {
  createRequestId,
  deliverBackground,
} from "../api/participantApi";
import type {
  ParticipantBackgroundRead,
  ParticipantViewState,
} from "../types/participant";

interface Props {
  view: ParticipantViewState;
  onDelivered: (
    background: ParticipantBackgroundRead,
  ) => Promise<void>;
}

export function MarketInformationScreen({
  view,
  onDelivered,
}: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleLoad() {
    setBusy(true);
    setError(null);

    try {
      const background = await deliverBackground(
        view.session_id,
        createRequestId(),
      );
      await onDelivered(background);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Unable to load market information.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="screen-shell screen-shell--focused">
      <section className="task-card">
        <span className="eyebrow">Market period preparation</span>
        <h1>Market Information</h1>
        <p className="lead-copy">
          Market information for this period is ready. Load the
          information before continuing with the current study task.
        </p>

        <div className="task-summary">
          <div>
            <span>Period</span>
            <strong>
              {view.period_number} of {view.period_count}
            </strong>
          </div>
          <div>
            <span>Market date</span>
            <strong>{view.current_date}</strong>
          </div>
          <div>
            <span>Status</span>
            <strong>
              {view.market.market_open ? "Open" : "Closed"}
            </strong>
          </div>
        </div>

        {error && <div className="error-banner">{error}</div>}

        <button
          className="primary-button"
          type="button"
          disabled={
            busy ||
            !view.allowed_actions.load_market_information
          }
          onClick={() => void handleLoad()}
        >
          {busy ? "Loading market information…" : "Load market information"}
        </button>
      </section>
    </main>
  );
}
