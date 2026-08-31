import type {
  ParticipantAssessmentCreate,
  ParticipantAssessmentRead,
  ParticipantBackgroundRead,
  ParticipantDecisionJourneyRead,
  ParticipantFeedbackRead,
  ParticipantInformationUpdateRead,
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
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });

  if (!response.ok) {
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

