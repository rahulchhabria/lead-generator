const BASE = '/api'

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...opts?.headers },
    ...opts,
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(err.detail || `HTTP ${resp.status}`)
  }
  if (resp.status === 204) return undefined as T
  return resp.json()
}

export const api = {
  campaigns: {
    list: () => request<CampaignSummary[]>('/campaigns/'),
    get: (id: string) => request<Campaign>(`/campaigns/${id}`),
    create: (body: CreateCampaignBody) =>
      request<{ campaign_id: string; job_id: string }>('/campaigns/', { method: 'POST', body: JSON.stringify(body) }),
    advance: (id: string) =>
      request<{ job_id: string }>(`/campaigns/${id}/advance`, { method: 'POST' }),
    getAccounts: (id: string) => request<Account[]>(`/campaigns/${id}/accounts`),
    getContacts: (id: string) => request<Contact[]>(`/campaigns/${id}/contacts`),
    getEmails: (id: string) => request<DraftEmail[]>(`/campaigns/${id}/emails`),
    reviewAccounts: (id: string, approved: number[], rejected: number[]) =>
      request(`/campaigns/${id}/accounts/review`, { method: 'POST', body: JSON.stringify({ approved_ids: approved, rejected_ids: rejected }) }),
    reviewContacts: (id: string, approved: number[], rejected: number[]) =>
      request(`/campaigns/${id}/contacts/review`, { method: 'POST', body: JSON.stringify({ approved_ids: approved, rejected_ids: rejected }) }),
    reviewEmails: (id: string, approved: number[], rejected: number[]) =>
      request(`/campaigns/${id}/emails/review`, { method: 'POST', body: JSON.stringify({ approved_ids: approved, rejected_ids: rejected }) }),
  },
  enrichment: {
    list: (limit = 50) => request<EnrichmentData[]>(`/enrichment/?limit=${limit}`),
    get: (domain: string) => request<EnrichmentData>(`/enrichment/${domain}`),
    single: (domain: string, company_name?: string, force_refresh = false) =>
      request<EnrichmentData>('/enrichment/single', { method: 'POST', body: JSON.stringify({ domain, company_name, force_refresh }) }),
    bulk: (domains: { domain: string; company_name?: string }[]) =>
      request<{ job_id: string; total: number }>('/enrichment/bulk', { method: 'POST', body: JSON.stringify({ domains }) }),
    upload: (file: File) => {
      const form = new FormData()
      form.append('file', file)
      return fetch(`${BASE}/enrichment/upload`, { method: 'POST', body: form }).then(r => r.json())
    },
  },
  accounts: {
    list: (limit = 100) => request<Account[]>(`/accounts/?limit=${limit}`),
    get: (id: number) => request<AccountDetail>(`/accounts/${id}`),
    enrich: (id: number) => request<{ job_id: string }>(`/accounts/${id}/enrich`, { method: 'POST' }),
  },
  contacts: {
    list: (limit = 100) => request<Contact[]>(`/contacts/?limit=${limit}`),
    get: (id: number) => request<ContactDetail>(`/contacts/${id}`),
  },
  exports: {
    campaignCsv: (id: string) => `${BASE}/exports/${id}/csv`,
    enrichmentCsv: () => `${BASE}/exports/enrichment/csv`,
  },
  jobs: {
    get: (id: string) => request<JobStatus>(`/jobs/${id}`),
    list: () => request<JobStatus[]>('/jobs/'),
  },
  health: () => request<{ status: string }>('/health'),
  status: () => request<ApiStatus>('/status'),
}

export interface CampaignSummary {
  id: string; current_stage: string; created_at: string; updated_at: string
  account_count: number; contact_count: number; approved_count: number
  has_icp: boolean; has_domains: boolean
}
export interface Campaign extends CampaignSummary {
  icp?: Record<string, unknown>; domains?: { domain: string; company_name?: string }[]; config?: Record<string, unknown>
}
export interface Account {
  id: number; campaign_id: string; company_name: string; domain: string
  industry?: string; employee_count?: string; location?: string; description?: string
  status: string; source: string; has_enrichment: boolean; created_at: string
}
export interface AccountDetail extends Account {
  relevance_reasoning?: string; enrichment?: EnrichmentData | null; contacts: Contact[]
}
export interface Contact {
  id: number; account_id: number; campaign_id: string; full_name: string
  title?: string; email?: string; email_confidence?: number; email_verified: boolean
  email_source?: string; status: string; linkedin_url?: string; company_name?: string; domain?: string; created_at: string
}
export interface ContactDetail extends Contact {
  first_name: string; last_name: string
  company?: { name?: string; domain?: string; industry?: string }
  dossier?: { github_username?: string; github_repos: string[]; github_languages: string[]; recent_posts: string[]; interests: string[]; education?: string; personal_details: string[] }
  emails: DraftEmail[]; account_enrichment?: EnrichmentData | null
}
export interface DraftEmail {
  id: number; contact_id: number; subject_line: string; body: string
  personalization_hooks: string[]; tone: string; status: string
  contact_name?: string; contact_email?: string; company_name?: string
}
export interface EnrichmentData {
  domain: string; company_name?: string; description?: string; long_description?: string
  founded_year?: number; employee_count?: number; employee_count_range?: string; engineering_count?: number
  hq_city?: string; hq_state?: string; hq_country?: string; industry?: string
  total_funding_raised?: string; latest_funding_round?: { type?: string; amount?: string; date?: string }
  ceo?: { name: string; linkedin_url?: string }; founders?: { name: string; role?: string }[]
  technographic?: { all_technologies: string[] }
  hiring?: { open_positions: number; top_skills: string[]; department_breakdown?: Record<string, number> }
  github_activity?: { total_stars: number; public_repos: number; programming_languages: string[] }
  mobile_apps?: { has_ios_app: boolean; has_android_app: boolean }
  ai_insights?: { recent_news: string[]; growth_stage?: string; competitive_landscape: string[]; key_differentiators: string[] }
  linkedin_url?: string; twitter_handle?: string; github_url?: string
  data_quality: string; confidence_score: number; last_enriched_at: string
}
export interface JobStatus {
  job_id: string; status: string; progress: number; message?: string
  result?: unknown; error?: string; created_at: string; updated_at: string
}
export interface ApiStatus { anthropic: boolean; serper: boolean; hunter: boolean; github: boolean }
export interface CreateCampaignBody {
  icp?: Record<string, unknown>; domains?: { domain: string }[]; target_roles?: string[]
  config?: Record<string, unknown>; auto_approve?: boolean
}
