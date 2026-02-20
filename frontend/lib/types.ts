/* ------------------------------------------------------------------ */
/*  TypeScript interfaces matching backend Pydantic models             */
/* ------------------------------------------------------------------ */

// ── Document / Ingest ──────────────────────────────────────────────

export interface ProcessedElement {
  element_id: string;
  element_type: string;
  text: string;
  html?: string | null;
  metadata: Record<string, unknown>;
  financial_data?: Record<string, unknown> | null;
  source_document: string;
  page_number: number;
}

export interface DocumentRecord {
  _id?: string;
  id?: string;
  filename: string;
  status: string;
  metadata: {
    source_filename?: string;
    file_size_bytes?: number;
    page_count?: number | null;
    content_type?: string;
    framework_tags?: string[];
    [key: string]: unknown;
  };
  chunks_count: number;
  elements_count: number;
  tables_count: number;
  total_pages: number;
  processing_time?: number | null;
  file_path?: string | null;
  sections?: Record<string, unknown>[];
  created_at?: string;
  updated_at?: string;
}

export interface UploadResponse {
  document_id: string;
  filename: string;
  status: string;
  message: string;
  elements_count: number;
  tables_count: number;
  pages: number;
  processing_time: number;
}

// ── Compliance ─────────────────────────────────────────────────────

export type ComplianceStatus =
  | "compliant"
  | "non_compliant"
  | "partially_compliant"
  | "not_applicable"
  | "unable_to_determine";

export interface ComplianceCheckResult {
  rule_id: string;
  rule_text: string;
  rule_source: string;
  framework: string;
  status: ComplianceStatus;
  confidence: number;
  evidence: string;
  evidence_location?: string;
  explanation: string;
  recommendations?: string | null;
}

export interface ComplianceReport {
  _id?: string;
  report_id: string;
  document_id: string;
  document_name: string;
  company_name?: string | null;
  fiscal_year?: string | null;
  frameworks_tested: string[];
  total_rules_checked: number;
  compliant_count: number;
  non_compliant_count: number;
  partially_compliant_count: number;
  not_applicable_count: number;
  unable_to_determine_count?: number;
  overall_compliance_score: number;
  results: ComplianceCheckResult[];
  summary: string;
  generated_at: string;
  processing_time: number;
  created_at?: string;
}

export interface FrameworkInfo {
  name: string;
  display_name: string;
  description: string;
  rule_count: number;
  collection?: string;
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

// ── Search ─────────────────────────────────────────────────────────

export interface SearchResult {
  text: string;
  score: number;
  metadata: Record<string, unknown>;
  collection: string;
}

export interface SearchRequest {
  query: string;
  collections: string[];
  top_k: number;
  filters?: Record<string, unknown>;
}

// ── Chat ───────────────────────────────────────────────────────────

export interface ChatSource {
  text: string;
  source: string;
  page?: number | null;
  section: string;
  score: number;
}

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
  sources?: ChatSource[];
  timestamp?: string;
}

export interface ChatSession {
  _id?: string;
  session_id: string;
  title: string;
  messages?: ChatMessage[];
  message_count?: number;
  last_message?: string;
  created_at?: string;
  updated_at?: string;
}

export interface ChatResponse {
  session_id: string;
  response: string;
  sources: ChatSource[];
  timestamp?: string;
}

// ── Dashboard / Stats ──────────────────────────────────────────────

export interface DashboardStats {
  documents_ingested: number;
  compliance_checks: number;
  average_score: number;
  active_frameworks: number;
}

// ── Analytics ──────────────────────────────────────────────────────

export interface AnalyticsDocument {
  document_id: string;
  filename: string;
  status: string;
  total_pages: number;
  tables_count: number;
  elements_count: number;
  created_at: string;
}

export interface AnalyseResponse {
  answer: string;
  charts: string[];
  metrics: Record<string, unknown>;
  tables_loaded: number;
}

export interface TableInfo {
  table_id: string;
  page_number: number;
  financial_statement_type: string | null;
  columns: string[];
  rows: number;
  has_html: boolean;
}

export interface TrendDataPoint {
  document_id: string;
  filename: string;
  fiscal_year: string;
  metric: string;
  value: number | null;
}

// ── Examination ────────────────────────────────────────────────────

export interface CompanyProfile {
  company_name: string;
  documents_count: number;
  compliance_reports_count: number;
  average_compliance_score: number;
  total_rules_checked: number;
  total_non_compliant: number;
  documents: Array<{
    document_id: string;
    filename: string;
    status: string;
    pages: number;
    created_at: string;
  }>;
  compliance_reports: Array<{
    report_id: string;
    document_name: string;
    score: number;
    frameworks: string[];
    non_compliant: number;
    created_at: string;
  }>;
}

export interface RiskDashboard {
  overall_risk: string;
  risk_score: number;
  categories: Array<{
    category: string;
    count: number;
    max_severity: string;
    items: Array<RiskFlag>;
  }>;
  flags: RiskFlag[];
  documents_analysed: number;
  reports_analysed: number;
}

export interface RiskFlag {
  type: string;
  severity: string;
  description: string;
  evidence?: string;
  source?: string;
}

export interface TimelineEvent {
  type: string;
  timestamp: string;
  title: string;
  description: string;
  document_id?: string;
  report_id?: string;
  score?: number;
  severity: string;
}

export interface ExaminationAnalysis {
  answer: string;
  company: string;
  data_summary: Record<string, unknown>;
}
