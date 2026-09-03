import { useCallback, useEffect, useMemo, useState } from "react";

import { getParticipantView } from "../api/participantApi";
import { ParticipantScreen } from "../screens/ParticipantScreen";
import type {
  ParticipantBackgroundRead,
  ParticipantInformationUpdateRead,
  ParticipantViewState,
} from "../types/participant";

interface Props {
  sessionId: string;
}

function storageKey(
  sessionId: string,
  kind: "background" | "information-update",
): string {
  return `marketlens:${sessionId}:${kind}`;
}

function readStored<T>(key: string): T | null {
  try {
    const value = localStorage.getItem(key);
    return value ? (JSON.parse(value) as T) : null;
  } catch {
    return null;
  }
}

export function ParticipantSession({
  sessionId,
}: Props) {
  const [view, setView] =
    useState<ParticipantViewState | null>(null);
  const [background, setBackground] =
    useState<ParticipantBackgroundRead | null>(() =>
      readStored<ParticipantBackgroundRead>(
        storageKey(sessionId, "background"),
      ),
    );
  const [informationUpdate, setInformationUpdate] =
    useState<ParticipantInformationUpdateRead | null>(() =>
      readStored<ParticipantInformationUpdateRead>(
        storageKey(sessionId, "information-update"),
      ),
    );
  const [initialLoading, setInitialLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshView = useCallback(async () => {
    setRefreshing(true);
    setError(null);

    try {
      setView(await getParticipantView(sessionId));
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Unable to load the participant session.",
      );
    } finally {
      setRefreshing(false);
      setInitialLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    void refreshView();
  }, [refreshView]);

  const currentBackground = useMemo(() => {
    if (!view || !background) {
      return null;
    }

    return background.current_date === view.current_date
      ? background
      : null;
  }, [background, view]);

  const currentInformationUpdate = useMemo(() => {
    if (!view || !informationUpdate) {
      return null;
    }

    return informationUpdate.current_date === view.current_date
      ? informationUpdate
      : null;
  }, [informationUpdate, view]);

  async function handleBackgroundDelivered(
    payload: ParticipantBackgroundRead,
  ) {
    setBackground(payload);
    localStorage.setItem(
      storageKey(sessionId, "background"),
      JSON.stringify(payload),
    );

    setInformationUpdate(null);
    localStorage.removeItem(
      storageKey(sessionId, "information-update"),
    );

    await refreshView();
  }

  async function handleInformationUpdateDelivered(
    payload: ParticipantInformationUpdateRead,
  ) {
    setInformationUpdate(payload);
    localStorage.setItem(
      storageKey(sessionId, "information-update"),
      JSON.stringify(payload),
    );

    await refreshView();
  }

  if (initialLoading && !view) {
    return (
      <main className="screen-shell screen-shell--focused">
        <section className="task-card">
          <span className="eyebrow">MarketLens</span>
          <h1>Loading participant session…</h1>
          <div className="loading-line" />
        </section>
      </main>
    );
  }

  if (!view) {
    return (
      <main className="screen-shell screen-shell--focused">
        <section className="task-card">
          <span className="eyebrow">Session unavailable</span>
          <h1>Unable to load this participant session</h1>

          {error && <div className="error-banner">{error}</div>}

          <button
            className="primary-button"
            type="button"
            onClick={() => void refreshView()}
          >
            Retry
          </button>
        </section>
      </main>
    );
  }

  return (
    <>
      {error && (
        <div className="global-error">
          <span>{error}</span>
          <button
            type="button"
            onClick={() => void refreshView()}
          >
            Retry
          </button>
        </div>
      )}

      {refreshing && (
        <div className="refresh-indicator">
          Updating session…
        </div>
      )}

      <ParticipantScreen
        view={view}
        background={currentBackground}
        informationUpdate={currentInformationUpdate}
        onBackgroundDelivered={handleBackgroundDelivered}
        onInformationUpdateDelivered={
          handleInformationUpdateDelivered
        }
        onMutationComplete={refreshView}
      />
    </>
  );
}
