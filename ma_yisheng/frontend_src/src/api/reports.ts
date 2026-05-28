import client, { API_BASE } from './client'

export interface Report {
  path: string
  project: string
  report_name: string
  mtime: number
  favorite: boolean
  scan_path: string
  language: string
  findings_count: number
  vuln_types: string[]
  severity: string
  files_analyzed: number
}

export interface CodeFlowStep {
  step: string
  line: number | null
  snippet: string
}

export interface Finding {
  file: string
  line: number
  column: number
  sink_rule: string
  sink_attribute: string
  vuln_name: string
  severity: '高危' | '中危' | '低危'
  message: string
  snippet: string
  code_flow: CodeFlowStep[]
  fingerprint: string
  engine?: string
  // AI review fields
  llm_verdict?: 'true_positive' | 'false_positive' | 'needs_review'
  llm_reason?: string
  llm_reviewed_at?: string
  // AI fix fields
  fix_explanation?: string
  fix_code?: string
  attack_scenario?: string
  fix_generated_at?: string
  // Exploit assessment fields
  exploitability?: string
  exploit_preconditions?: string
  exploit_attack_path?: string
  exploit_poc_hint?: string
  exploit_impact?: string
  exploit_difficulty?: string
  exploit_assessed_at?: string
}

export const listReports = (limit = 50, project = '') =>
  client.get<{ reports: Report[] }>('/api/reports', { params: { limit, project } })

export const getReportContent = (reportPath: string) =>
  client.get<{ content: string }>(`/api/reports/${encodeURIComponent(reportPath)}/content`)

export const getFindings = (reportPath: string) =>
  client.get<{ findings: Finding[]; count: number; disclaimer: string }>(
    `/api/reports/${encodeURIComponent(reportPath)}/findings`
  )

export const reviewFinding = (reportPath: string, index: number) =>
  client.post<{ ok: boolean; index: number; fingerprint: string; verdict: string; verdict_label: string; reason: string }>(
    `/api/reports/${encodeURIComponent(reportPath)}/findings/review`,
    { index }
  )

export const fixFinding = (reportPath: string, index: number) =>
  client.post<{ ok: boolean; index: number; fingerprint: string; explanation: string; fix_code: string; attack_scenario: string }>(
    `/api/reports/${encodeURIComponent(reportPath)}/findings/fix`,
    { index }
  )

export const exploitFinding = (reportPath: string, index: number) =>
  client.post<{
    ok: boolean; index: number; fingerprint: string
    exploitability: string; preconditions: string; attack_path: string
    poc_hint: string; impact: string; difficulty: string
  }>(
    `/api/reports/${encodeURIComponent(reportPath)}/findings/exploit`,
    { index }
  )

export const logicAudit = (reportPath: string) =>
  client.post<{
    ok: boolean; report_path: string; files_analyzed: number
    chars_analyzed: number; issues: string[]; issues_count: number; summary: string
  }>(`/api/reports/${encodeURIComponent(reportPath)}/logic-audit`)

export const toggleFavorite = (reportPath: string) =>
  client.post<{ ok: boolean; favorite: boolean }>(`/api/reports/${encodeURIComponent(reportPath)}/favorite`)

export const getExportUrl = (reportPath: string) =>
  `${API_BASE}/api/reports/${encodeURIComponent(reportPath)}/export`

export const deleteReport = (reportPath: string) =>
  client.delete<{ ok: boolean }>(`/api/reports/${encodeURIComponent(reportPath)}`)

export const getChatStreamUrl = (reportPath: string) =>
  `${API_BASE}/api/reports/${encodeURIComponent(reportPath)}/chat/stream`
