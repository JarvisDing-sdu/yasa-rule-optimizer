import client from './client'

export interface RuleSetSummary {
  id: number | string
  name: string
  description?: string
  source_type?: string
  lang: string
  scene?: string
  rule_count?: number
  is_official?: boolean
}

export const listRuleSets = () =>
  client.get<{ rule_sets: RuleSetSummary[]; count: number }>('/api/rule-sets', {
    params: { include_official: true },
  })
