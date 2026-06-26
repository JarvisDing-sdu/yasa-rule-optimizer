import client from './client'

export type RuntimeConfig = {
  YASA_BUNDLE_PATH: string
  YASA_EXECUTABLE: string
  UAST_PYTHON_EXE: string
  UAST_GO_EXE: string
  LLM_PROVIDER: string
  LLM_BASE_URL: string
  LLM_API_KEY: string
  LLM_MODEL: string
  SERVER_URL: string
  GITHUB_TOKEN: string
  SEMGREP_RULES_PATH: string
  SCAN_TIMEOUT: string
  SMTP_HOST: string
  SMTP_PORT: string
  SMTP_USER: string
  SMTP_PASSWORD: string
  SMTP_FROM_NAME: string
  SMTP_SECURITY: string
}

export async function getRuntimeConfig() {
  return client.get<{
    values: Partial<RuntimeConfig>
    configured: { yasa: boolean; llm: boolean }
    missing: string[]
    editable?: boolean
  }>('/api/config')
}

export async function saveRuntimeConfig(values: RuntimeConfig) {
  return client.post<{
    ok: boolean
    configured: { yasa: boolean; llm: boolean }
    missing: string[]
  }>('/api/config', values)
}

export async function testMail(to_email: string) {
  return client.post<{ ok: boolean; message: string }>('/api/config/test-mail', { to_email })
}

export async function clearLoginLocks() {
  return client.post<{ ok: boolean; message: string }>('/api/config/clear-login-locks')
}
