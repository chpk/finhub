/* ------------------------------------------------------------------ */
/*  Typed API client for the NFRA Compliance Engine backend            */
/* ------------------------------------------------------------------ */

import type {
  ChatResponse,
  ChatSession,
  ComplianceReport,
  DashboardStats,
  DocumentRecord,
  FrameworkInfo,
  SearchResult,
  UploadResponse,
} from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";

/* ── Persistent client-side cache (survives SPA navigation) ──────── */

const _memCache = new Map<string, { data: unknown; expires: number }>();
const DEFAULT_TTL = 60_000; // 60 seconds

function _ssKey(key: string): string {
  return `nfra_cache_${key}`;
}

function getCached<T>(key: string): T | null {
  const mem = _memCache.get(key);
  if (mem && Date.now() < mem.expires) return mem.data as T;
  _memCache.delete(key);
  if (typeof sessionStorage === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(_ssKey(key));
    if (!raw) return null;
    const entry = JSON.parse(raw) as { data: unknown; expires: number };
    if (Date.now() < entry.expires) {
      _memCache.set(key, entry);
      return entry.data as T;
    }
    sessionStorage.removeItem(_ssKey(key));
  } catch { /* ignore */ }
  return null;
}

function setCache(key: string, data: unknown, ttl = DEFAULT_TTL): void {
  const entry = { data, expires: Date.now() + ttl };
  _memCache.set(key, entry);
  if (typeof sessionStorage !== "undefined") {
    try { sessionStorage.setItem(_ssKey(key), JSON.stringify(entry)); } catch { /* quota */ }
  }
}

export function invalidateCache(prefix?: string): void {
  if (!prefix) {
    _memCache.clear();
    if (typeof sessionStorage !== "undefined") {
      const keys = Object.keys(sessionStorage).filter(k => k.startsWith("nfra_cache_"));
      keys.forEach(k => sessionStorage.removeItem(k));
    }
    return;
  }
  for (const key of _memCache.keys()) {
    if (key.startsWith(prefix)) _memCache.delete(key);
  }
  if (typeof sessionStorage !== "undefined") {
    const keys = Object.keys(sessionStorage).filter(k => k.startsWith(`nfra_cache_${prefix}`));
    keys.forEach(k => sessionStorage.removeItem(k));
  }
}

/* ── Helpers ──────────────────────────────────────────────────────── */

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(
      `API ${res.status}: ${res.statusText}${body ? ` — ${body}` : ""}`
    );
  }

  if (res.status === 204) return undefined as unknown as T;
  return res.json() as Promise<T>;
}

async function cachedRequest<T>(
  path: string,
  ttl = DEFAULT_TTL,
): Promise<T> {
  const cached = getCached<T>(path);
  if (cached) return cached;
  const data = await request<T>(path);
  setCache(path, data, ttl);
  return data;
}

/**
 * Stale-while-revalidate: return stale data instantly if available,
 * then refresh in the background. If no stale data, fetch fresh.
 */
async function swrRequest<T>(
  path: string,
  ttl = DEFAULT_TTL,
): Promise<T> {
  const cached = getCached<T>(path);
  if (cached) {
    request<T>(path).then(fresh => setCache(path, fresh, ttl)).catch(() => {});
    return cached;
  }
  const data = await request<T>(path);
  setCache(path, data, ttl);
  return data;
}

/* ── Ingest ───────────────────────────────────────────────────────── */

export async function uploadDocument(
  file: File,
  docType: string = "auto"
): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("doc_type", docType);

  const res = await fetch(`${API_BASE}/api/ingest/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Upload failed ${res.status}: ${text}`);
  }
  return res.json();
}

export async function getDocuments(
  skip = 0,
  limit = 50
): Promise<DocumentRecord[]> {
  return swrRequest<DocumentRecord[]>(
    `/api/ingest/documents?skip=${skip}&limit=${limit}`,
    45_000,
  );
}

export async function getDocumentStatus(
  docId: string
): Promise<DocumentRecord> {
  return request<DocumentRecord>(`/api/ingest/status/${docId}`);
}

/* ── Compliance ───────────────────────────────────────────────────── */

export async function runComplianceCheck(
  documentId: string,
  frameworks: string[],
  sections?: string[]
): Promise<ComplianceReport> {
  return request<ComplianceReport>("/api/compliance/check", {
    method: "POST",
    body: JSON.stringify({
      document_id: documentId,
      frameworks,
      sections: sections || null,
    }),
  });
}

export async function runComplianceCheckAsync(
  documentId: string,
  frameworks: string[],
  sections?: string[]
): Promise<{ job_id: string; status: string }> {
  return request<{ job_id: string; status: string }>(
    "/api/compliance/check/async",
    {
      method: "POST",
      body: JSON.stringify({
        document_id: documentId,
        frameworks,
        sections: sections || null,
      }),
    }
  );
}

export interface ComplianceProgress {
  job_id: string;
  document_id: string;
  frameworks: string[];
  status: string;
  steps: Array<{ step: string; pct: number; timestamp: string }>;
  current_step: string;
  progress_pct: number;
  report_id: string | null;
  error: string | null;
}

export async function getComplianceProgress(
  jobId: string
): Promise<ComplianceProgress> {
  return request<ComplianceProgress>(
    `/api/compliance/check/progress/${jobId}`
  );
}

export async function getComplianceReports(
  skip = 0,
  limit = 50
): Promise<ComplianceReport[]> {
  return swrRequest<ComplianceReport[]>(
    `/api/compliance/reports?skip=${skip}&limit=${limit}`,
    45_000,
  );
}

export async function getComplianceReport(
  reportId: string
): Promise<ComplianceReport> {
  return request<ComplianceReport>(`/api/compliance/reports/${reportId}`);
}

export async function getFrameworks(): Promise<FrameworkInfo[]> {
  return swrRequest<FrameworkInfo[]>("/api/compliance/frameworks", 120_000);
}

/* ── Search ───────────────────────────────────────────────────────── */

export async function searchDocuments(
  query: string,
  collections: string[] = [],
  topK = 10,
  filters?: Record<string, unknown>
): Promise<SearchResult[]> {
  return request<SearchResult[]>("/api/search/query", {
    method: "POST",
    body: JSON.stringify({
      query,
      collections,
      top_k: topK,
      filters: filters || {},
    }),
  });
}

/* ── Chat ─────────────────────────────────────────────────────────── */

export async function sendChatMessage(
  message: string,
  sessionId?: string | null,
  documentContext: string[] = []
): Promise<ChatResponse> {
  return request<ChatResponse>("/api/chat/message", {
    method: "POST",
    body: JSON.stringify({
      session_id: sessionId || null,
      message,
      document_context: documentContext,
    }),
  });
}

export async function getChatSessions(
  skip = 0,
  limit = 20
): Promise<ChatSession[]> {
  return swrRequest<ChatSession[]>(
    `/api/chat/sessions?skip=${skip}&limit=${limit}`,
    30_000,
  );
}

export async function getChatHistory(
  sessionId: string
): Promise<ChatSession> {
  return request<ChatSession>(`/api/chat/sessions/${sessionId}`);
}

export async function deleteChatSession(
  sessionId: string
): Promise<void> {
  return request<void>(`/api/chat/sessions/${sessionId}`, {
    method: "DELETE",
  });
}

/* ── Dashboard ────────────────────────────────────────────────────── */

export async function getDashboardStats(): Promise<DashboardStats> {
  try {
    return await swrRequest<DashboardStats>(
      "/api/dashboard/stats",
      30_000,
    );
  } catch {
    return {
      documents_ingested: 0,
      compliance_checks: 0,
      average_score: 0,
      active_frameworks: 0,
    };
  }
}

/* ── Report Downloads ─────────────────────────────────────────────── */

async function downloadFile(path: string, filename: string): Promise<void> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Download failed ${res.status}: ${text}`);
  }
  const blob = await res.blob();
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  link.click();
  URL.revokeObjectURL(link.href);
}

export async function downloadReportJson(reportId: string): Promise<void> {
  return downloadFile(
    `/api/reports/${reportId}/json`,
    `compliance-report-${reportId.slice(0, 8)}.json`
  );
}

export async function downloadReportPdf(reportId: string): Promise<void> {
  return downloadFile(
    `/api/reports/${reportId}/pdf`,
    `compliance-report-${reportId.slice(0, 8)}.pdf`
  );
}

export async function downloadReportExcel(reportId: string): Promise<void> {
  return downloadFile(
    `/api/reports/${reportId}/excel`,
    `compliance-report-${reportId.slice(0, 8)}.xlsx`
  );
}

export async function getReportSummary(
  reportId: string
): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>(
    `/api/reports/${reportId}/summary`
  );
}

/* ── Analytics ─────────────────────────────────────────────────────── */

import type {
  AnalyticsDocument,
  AnalyseResponse,
  TableInfo,
  TrendDataPoint,
  CompanyProfile,
  RiskDashboard,
  TimelineEvent,
  ExaminationAnalysis,
} from "./types";

export async function getAnalyticsDocuments(
  skip = 0,
  limit = 50
): Promise<AnalyticsDocument[]> {
  return swrRequest<AnalyticsDocument[]>(
    `/api/analytics/documents?skip=${skip}&limit=${limit}`,
    45_000,
  );
}

export async function getDocumentTables(
  documentId: string
): Promise<TableInfo[]> {
  return request<TableInfo[]>(`/api/analytics/documents/${documentId}/tables`);
}

export async function analyseData(
  question: string,
  documentIds?: string[]
): Promise<AnalyseResponse> {
  return request<AnalyseResponse>("/api/analytics/analyse", {
    method: "POST",
    body: JSON.stringify({
      question,
      document_ids: documentIds || null,
    }),
  });
}

export async function getFinancialMetrics(
  documentIds?: string[]
): Promise<Record<string, unknown>> {
  const idsParam = documentIds?.join(",") || "";
  return request<Record<string, unknown>>(
    `/api/analytics/metrics?document_ids=${idsParam}`
  );
}

export async function getRiskIndicators(
  documentId: string
): Promise<Array<Record<string, unknown>>> {
  return request<Array<Record<string, unknown>>>(
    `/api/analytics/risk/${documentId}`
  );
}

export async function getTrendData(
  documentIds: string[],
  metric: string
): Promise<TrendDataPoint[]> {
  return request<TrendDataPoint[]>("/api/analytics/trend", {
    method: "POST",
    body: JSON.stringify({ document_ids: documentIds, metric }),
  });
}

export async function compareDocuments(
  documentIds: string[],
  metrics: string[]
): Promise<Record<string, TrendDataPoint[]>> {
  return request<Record<string, TrendDataPoint[]>>("/api/analytics/compare", {
    method: "POST",
    body: JSON.stringify({ document_ids: documentIds, metrics }),
  });
}

/* ── Examination ──────────────────────────────────────────────────── */

export async function getCompanyProfile(
  companyName: string
): Promise<CompanyProfile> {
  return request<CompanyProfile>(
    `/api/examination/company/${encodeURIComponent(companyName)}`
  );
}

export async function getRiskDashboard(
  documentId?: string
): Promise<RiskDashboard> {
  const param = documentId ? `?document_id=${documentId}` : "";
  return request<RiskDashboard>(`/api/examination/risk${param}`);
}

export async function getComplianceTimeline(
  company?: string
): Promise<TimelineEvent[]> {
  const param = company ? `?company=${encodeURIComponent(company)}` : "";
  return request<TimelineEvent[]>(`/api/examination/timeline${param}`);
}

export async function examineCompany(
  companyName: string,
  question: string
): Promise<ExaminationAnalysis> {
  return request<ExaminationAnalysis>("/api/examination/analyse", {
    method: "POST",
    body: JSON.stringify({ company_name: companyName, question }),
  });
}

/* ── Enhanced Chat ────────────────────────────────────────────────── */

export async function sendAnalyticsChatMessage(
  message: string,
  sessionId?: string | null,
  documentIds: string[] = [],
  mode: string = "auto"
): Promise<ChatResponse> {
  return request<ChatResponse>("/api/chat/message/analytics", {
    method: "POST",
    body: JSON.stringify({
      session_id: sessionId || null,
      message,
      document_ids: documentIds,
      mode,
    }),
  });
}

/* ── Health ────────────────────────────────────────────────────────── */

export async function checkHealth(): Promise<{ status: string }> {
  return request<{ status: string }>("/api/health");
}
