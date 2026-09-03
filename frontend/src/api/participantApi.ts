import type {
  ParticipantAssessmentCreate,
  ParticipantAuthLoginRead,
  ParticipantAuthSession,
  ParticipantAssessmentRead,
  ParticipantBackgroundRead,
  ParticipantDecisionJourneyRead,
  ParticipantFeedbackRead,
  ParticipantInformationUpdateRead,
  ParticipantMarketOverviewRead,
  ParticipantViewState,
  PortfolioOrderCreate,
  PortfolioOrderPreviewCreate,
  PortfolioOrderPreviewRead,
  PortfolioRead,
  PortfolioTransactionRead,
  SessionRead,
} from "../types/participant";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/+$/, "") ??
  "http://localhost:8000";

const AUTH_STORAGE_KEY = "marketlens:formal-auth:v1";

export const AUTH_REQUIRED_EVENT =
  "marketlens:formal-auth-required";

export function readParticipantAuthSession():
  | ParticipantAuthSession
  | null {
  try {
    const raw = sessionStorage.getItem(AUTH_STORAGE_KEY);

    if (!raw) {
      return null;
    }

    const parsed = JSON.parse(raw) as Partial<ParticipantAuthSession>;

    if (
      typeof parsed.participant_id !== "string" ||
      typeof parsed.session_id !== "string" ||
      typeof parsed.access_token !== "string" ||
      typeof parsed.expires_at !== "string"
    ) {
      sessionStorage.removeItem(AUTH_STORAGE_KEY);
      return null;
    }

    const expiresAt = Date.parse(parsed.expires_at);

    if (
      !Number.isFinite(expiresAt) ||
      expiresAt <= Date.now()
    ) {
      sessionStorage.removeItem(AUTH_STORAGE_KEY);
      return null;
    }

    return {
      participant_id: parsed.participant_id,
      session_id: parsed.session_id,
      access_token: parsed.access_token,
      expires_at: parsed.expires_at,
    };
  } catch {
    sessionStorage.removeItem(AUTH_STORAGE_KEY);
    return null;
  }
}

export function writeParticipantAuthSession(
  auth: ParticipantAuthSession,
): void {
  sessionStorage.setItem(
    AUTH_STORAGE_KEY,
    JSON.stringify(auth),
  );
}

export function clearParticipantAuthSession(): void {
  sessionStorage.removeItem(AUTH_STORAGE_KEY);
}

export class ParticipantApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ParticipantApiError";
    this.status = status;
  }
}

async function requestJson<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const auth = readParticipantAuthSession();

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(auth
        ? { Authorization: `Bearer ${auth.access_token}` }
        : {}),
      ...options.headers,
    },
  });

  if (!response.ok) {
    if (
      response.status === 401 &&
      path !== "/auth/login"
    ) {
      clearParticipantAuthSession();
      window.dispatchEvent(
        new Event(AUTH_REQUIRED_EVENT),
      );
    }

    let message = `Request failed with status ${response.status}`;

    try {
      const payload = (await response.json()) as {
        detail?: unknown;
      };

      if (typeof payload.detail === "string") {
        message = payload.detail;
      }
    } catch {
      // Keep the HTTP fallback message.
    }

    throw new ParticipantApiError(message, response.status);
  }

  return (await response.json()) as T;
}

function sessionPath(sessionId: string): string {
  return `/session/${encodeURIComponent(sessionId)}`;
}

export function createRequestId(): string {
  return crypto.randomUUID();
}

export function loginParticipant(
  participantId: string,
  password: string,
): Promise<ParticipantAuthLoginRead> {
  return requestJson<ParticipantAuthLoginRead>(
    "/auth/login",
    {
      method: "POST",
      body: JSON.stringify({
        participant_id: participantId,
        password,
      }),
    },
  );
}

export function createParticipantSession(
  participantId: string,
  requestId: string,
): Promise<SessionRead> {
  return requestJson<SessionRead>("/participant-session", {
    method: "POST",
    body: JSON.stringify({
      participant_id: participantId,
      request_id: requestId,
    }),
  });
}

export function getParticipantView(
  sessionId: string,
): Promise<ParticipantViewState> {
  return requestJson<ParticipantViewState>(
    `${sessionPath(sessionId)}/view`,
  );
}

export function getMarketOverview(
  sessionId: string,
): Promise<ParticipantMarketOverviewRead> {
  return requestJson<ParticipantMarketOverviewRead>(
    `${sessionPath(sessionId)}/market-overview`,
  );
}

export function deliverBackground(
  sessionId: string,
  requestId: string,
): Promise<ParticipantBackgroundRead> {
  return requestJson<ParticipantBackgroundRead>(
    `${sessionPath(sessionId)}/exposure/background`,
    {
      method: "POST",
      body: JSON.stringify({ request_id: requestId }),
    },
  );
}

export function deliverInformationUpdate(
  sessionId: string,
  requestId: string,
): Promise<ParticipantInformationUpdateRead> {
  return requestJson<ParticipantInformationUpdateRead>(
    `${sessionPath(sessionId)}/information-update`,
    {
      method: "POST",
      body: JSON.stringify({ request_id: requestId }),
    },
  );
}

export function submitAssessment(
  sessionId: string,
  payload: ParticipantAssessmentCreate,
): Promise<ParticipantAssessmentRead> {
  return requestJson<ParticipantAssessmentRead>(
    `${sessionPath(sessionId)}/assessment`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export function getPortfolio(
  sessionId: string,
): Promise<PortfolioRead> {
  return requestJson<PortfolioRead>(
    `${sessionPath(sessionId)}/portfolio`,
  );
}

export function previewPortfolioOrder(
  sessionId: string,
  payload: PortfolioOrderPreviewCreate,
): Promise<PortfolioOrderPreviewRead> {
  return requestJson<PortfolioOrderPreviewRead>(
    `${sessionPath(sessionId)}/portfolio/preview`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export function submitPortfolioOrder(
  sessionId: string,
  payload: PortfolioOrderCreate,
): Promise<PortfolioTransactionRead> {
  return requestJson<PortfolioTransactionRead>(
    `${sessionPath(sessionId)}/portfolio/order`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export function completeRound(
  sessionId: string,
  requestId: string,
  step: number,
): Promise<unknown> {
  return requestJson(
    `${sessionPath(sessionId)}/round/complete`,
    {
      method: "POST",
      body: JSON.stringify({
        request_id: requestId,
        step,
      }),
    },
  );
}

export function getCurrentFeedback(
  sessionId: string,
): Promise<ParticipantFeedbackRead> {
  return requestJson<ParticipantFeedbackRead>(
    `${sessionPath(sessionId)}/feedback/current`,
  );
}

export function continueCurrentFeedback(
  sessionId: string,
  requestId: string,
): Promise<{ continued: boolean }> {
  return requestJson<{ continued: boolean }>(
    `${sessionPath(sessionId)}/feedback/current/continue`,
    {
      method: "POST",
      body: JSON.stringify({ request_id: requestId }),
    },
  );
}

export function getDecisionJourney(
  sessionId: string,
): Promise<ParticipantDecisionJourneyRead> {
  return requestJson<ParticipantDecisionJourneyRead>(
    `${sessionPath(sessionId)}/journey`,
  );
}

export function completeDebrief(
  sessionId: string,
): Promise<ParticipantViewState> {
  return requestJson<ParticipantViewState>(
    `${sessionPath(sessionId)}/debrief/complete`,
    {
      method: "POST",
    },
  );
}

