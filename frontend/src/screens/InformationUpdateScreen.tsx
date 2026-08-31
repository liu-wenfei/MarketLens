import { useState } from "react";

import {
  createRequestId,
  deliverInformationUpdate,
} from "../api/participantApi";
import type {
  ParticipantBackgroundRead,
  ParticipantInformationUpdateRead,
  ParticipantViewState,
} from "../types/participant";
import { MarketContext } from "../components/MarketContext";

interface Props {
  view: ParticipantViewState;
  background: ParticipantBackgroundRead | null;
  onDelivered: (
    update: ParticipantInformationUpdateRead,
  ) => Promise<void>;
}

export function InformationUpdateScreen({
  view,
  background,
  onDelivered,
}: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleLoad() {
    setBusy(true);
    setError(null);

    try {
      const update = await deliverInformationUpdate(
        view.session_id,
        createRequestId(),
      );
      await onDelivered(update);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Unable to load the information update.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="screen-shell">
      <div className="screen-title">
        <span className="eyebrow">Current task</span>
        <h1>New Market Information</h1>
        <p>
          A new item of market information is ready for this market period.
        </p>
      </div>

      <MarketContext
        view={view}
        background={background}
      />

      <section className="panel action-panel">
        {error && <div className="error-banner">{error}</div>}

        <button
          className="primary-button"
          type="button"
          disabled={
            busy ||
            !view.allowed_actions.load_information_update
          }
          onClick={() => void handleLoad()}
        >
          {busy ? "Loading information…" : "Load information update"}
        </button>
      </section>
    </main>
  );
}
