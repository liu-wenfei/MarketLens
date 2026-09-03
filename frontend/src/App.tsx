import { useEffect, useState } from "react";

import {
  AUTH_REQUIRED_EVENT,
  clearParticipantAuthSession,
  loginParticipant,
  readParticipantAuthSession,
  writeParticipantAuthSession,
} from "./api/participantApi";
import { ParticipantSession } from "./session/ParticipantSession";
import type {
  ParticipantAuthSession,
} from "./types/participant";
import "./App.css";

function removeLegacySessionIdFromUrl(): void {
  const url = new URL(window.location.href);

  if (!url.searchParams.has("session_id")) {
    return;
  }

  url.searchParams.delete("session_id");
  window.history.replaceState({}, "", url);
}

function ParticipantStart({
  onAuthenticated,
}: {
  onAuthenticated: (
    auth: ParticipantAuthSession,
  ) => void;
}) {
  const [participantId, setParticipantId] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleStart() {
    const idValue = participantId.trim();
    const passwordValue = password.trim();

    if (!idValue) {
      setError(
        "Enter the participant ID provided by the researcher.",
      );
      return;
    }

    if (!passwordValue) {
      setError(
        "Enter the password provided by the researcher.",
      );
      return;
    }

    setBusy(true);
    setError(null);

    try {
      const login = await loginParticipant(
        idValue,
        passwordValue,
      );

      const auth: ParticipantAuthSession = {
        participant_id: login.session.participant_id,
        session_id: login.session.session_id,
        access_token: login.access_token,
        expires_at: login.expires_at,
      };

      writeParticipantAuthSession(auth);
      setPassword("");
      onAuthenticated(auth);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Unable to open the participant session.",
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
          Use the participant ID and password provided by the
          researcher. If you return later, sign in again with the same
          details to resume the same study session.
        </div>

        <div className="form-section">
          <label htmlFor="participant-id">Participant ID</label>
          <input
            id="participant-id"
            value={participantId}
            autoComplete="username"
            autoCapitalize="characters"
            onChange={(event) =>
              setParticipantId(event.target.value)
            }
            placeholder="Enter participant ID"
          />
        </div>

        <div className="form-section">
          <label htmlFor="participant-password">Password</label>
          <input
            id="participant-password"
            type="password"
            value={password}
            autoComplete="current-password"
            onChange={(event) =>
              setPassword(event.target.value)
            }
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                void handleStart();
              }
            }}
            placeholder="Enter password"
          />
        </div>

        {error && <div className="error-banner">{error}</div>}

        <button
          className="primary-button"
          type="button"
          disabled={busy}
          onClick={() => void handleStart()}
        >
          {busy ? "Opening session…" : "Open MarketLens session"}
        </button>
      </main>
    </div>
  );
}

function App() {
  const [auth, setAuth] =
    useState<ParticipantAuthSession | null>(
      readParticipantAuthSession,
    );

  useEffect(() => {
    removeLegacySessionIdFromUrl();

    function requireAuthentication() {
      clearParticipantAuthSession();
      setAuth(null);
    }

    window.addEventListener(
      AUTH_REQUIRED_EVENT,
      requireAuthentication,
    );

    return () => {
      window.removeEventListener(
        AUTH_REQUIRED_EVENT,
        requireAuthentication,
      );
    };
  }, []);

  if (!auth) {
    return (
      <ParticipantStart
        onAuthenticated={setAuth}
      />
    );
  }

  return (
    <ParticipantSession
      sessionId={auth.session_id}
    />
  );
}

export default App;
