import type {
  AlertIngestRequest,
  AlertIngestResponse,
  CaseEnvelope,
  CaseSummary,
  CorpusVersion,
  EvalRunSummary,
  OverrideRequest,
  RetrievalDebugResponse,
  TriageJobRequest,
  TriageJobResponse,
} from "./contracts";

function getBaseUrl(): string {
  if (typeof window === "undefined") {
    return process.env.API_URL ?? "http://localhost:8000";
  }
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
}

class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, body: unknown, message: string) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${getBaseUrl()}${path}`, {
    ...init,
    headers: {
      "content-type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      body = await res.text();
    }
    throw new ApiError(res.status, body, `${init?.method ?? "GET"} ${path} -> ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  ingestAlert: (body: AlertIngestRequest) =>
    request<AlertIngestResponse>("/alerts", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  submitTriage: (body: TriageJobRequest) =>
    request<TriageJobResponse>("/triage/jobs", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  listCases: (limit = 50) => request<CaseSummary[]>(`/cases?limit=${limit}`),

  getCase: (caseId: string) => request<CaseEnvelope>(`/cases/${encodeURIComponent(caseId)}`),

  postOverride: (caseId: string, body: OverrideRequest) =>
    request<CaseEnvelope>(`/cases/${encodeURIComponent(caseId)}/override`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  latestEval: () => request<EvalRunSummary>("/eval/latest"),

  debugRetrieval: (query: string, topK = 4) =>
    request<RetrievalDebugResponse>(
      `/retrieval/debug?query=${encodeURIComponent(query)}&top_k=${topK}`,
    ),

  listCorpusVersions: () => request<CorpusVersion[]>("/corpus/versions"),
};

export { ApiError };
