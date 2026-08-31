import { useState } from "react";

import {
  createParticipantSession,
  createRequestId,
} from "./api/participantApi";
import { ParticipantSession } from "./session/ParticipantSession";
import "./App.css";

function sessionFromUrl(): string | null {
  const value = new URLSearchParams(window.location.search).get(
    "session_id",
  );

  return value?.trim() || null;
}

function ParticipantStart({
  onStarted,
}: {
  onStarted: (sessionId: string) => void;
}) {
  const [participantId, setParticipantId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleStart() {
    const value = participantId.trim();

    if (!value) {
      setError("Enter the participant ID provided by the researcher.");
      return;
    }

    setBusy(true);
    setError(null);

    try {
      const session = await createParticipantSession(
        value,
        createRequestId(),
      );
      onStarted(session.session_id);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Unable to start the participant session.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="start-page">
      <div className="start-page__brand">
        <span className="study-header__mark">ML</span>
        <strong>MarketLens</strong>
      </div>

      <main className="start-card">
        <span className="eyebrow">Participant study</span>
        <h1>Welcome to MarketLens</h1>

        <p className="lead-copy">
          You will review a simulated financial market, record your
          assessments, and manage a simulated portfolio across a series
          of market periods.
        </p>

        <div className="start-note">
          Your participant ID is used only to open your assigned study
          session. Market conditions and study progression are controlled
          by the study server.
        </div>

        <div className="form-section">
          <label htmlFor="participant-id">Participant ID</label>
          <input
            id="participant-id"
            value={participantId}
            autoComplete="off"
            onChange={(event) =>
              setParticipantId(event.target.value)
            }
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                void handleStart();
              }
            }}
            placeholder="Enter participant ID"
          />
        </div>

        {error && <div className="error-banner">{error}</div>}

        <button
          className="primary-button"
          type="button"
          disabled={busy}
          onClick={() => void handleStart()}
        >
          {busy ? "Starting session…" : "Start MarketLens session"}
        </button>
      </main>
    </div>
  );
}

function App() {
  const [sessionId, setSessionId] = useState<string | null>(
    sessionFromUrl,
  );

  function handleStarted(value: string) {
    const url = new URL(window.location.href);
    url.searchParams.set("session_id", value);
    window.history.replaceState({}, "", url);

    setSessionId(value);
  }

  if (!sessionId) {
    return <ParticipantStart onStarted={handleStarted} />;
  }

  return <ParticipantSession sessionId={sessionId} />;
}

export default App;
