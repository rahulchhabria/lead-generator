import { useState, useRef } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, EnrichmentData, Contact } from '../api/client'
import { Card, CardHeader, CardBody } from '../components/Card'
import { Badge } from '../components/Badge'
import { EnrichmentCard } from '../components/EnrichmentCard'
import { JobPoller } from '../components/JobPoller'
import { Search, Upload, Download, X, Loader2, RefreshCw, Users } from 'lucide-react'

// ── Domain Contacts ──────────────────────────────────────────────────────────

function DomainContacts({ domain }: { domain: string }) {
  const { data: contacts = [] } = useQuery({
    queryKey: ['contacts-by-domain', domain],
    queryFn: () => api.contacts.byDomain(domain),
    staleTime: 30_000,
  })
  if (contacts.length === 0) return null
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Users size={15} className="text-gray-500" />
          <h3 className="font-semibold text-sm">Contacts ({contacts.length})</h3>
        </div>
      </CardHeader>
      <div className="divide-y divide-gray-100">
        {contacts.map(c => (
          <Link key={c.id} to={`/contacts/${c.id}`} className="flex items-center justify-between px-6 py-3 hover:bg-gray-50">
            <div>
              <p className="text-sm font-medium">{c.full_name}</p>
              <p className="text-xs text-gray-500">{c.title}{c.email ? ` · ${c.email}` : ''}</p>
            </div>
            <Badge label={c.status} />
          </Link>
        ))}
      </div>
    </Card>
  )
}

// ── Enrich Modal ─────────────────────────────────────────────────────────────

function EnrichModal({ onClose }: { onClose: () => void }) {
  const [domain, setDomain] = useState('')
  const [companyName, setCompanyName] = useState('')
  const [result, setResult] = useState<EnrichmentData | null>(null)
  const qc = useQueryClient()

  const { mutate, isPending, isError, error } = useMutation({
    mutationFn: () => api.enrichment.single(domain.trim(), companyName.trim() || undefined),
    onSuccess: (data) => {
      setResult(data)
      qc.invalidateQueries({ queryKey: ['enrichments'] })
    },
  })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 flex-shrink-0">
          <h3 className="text-lg font-semibold text-gray-900">{result ? (result.company_name || result.domain) : 'Enrich Domain'}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={20} /></button>
        </div>

        <div className="overflow-y-auto flex-1 p-6 space-y-6">
          {!result && (
            <div className="space-y-4">
              <div className="grid sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Domain *</label>
                  <input
                    autoFocus
                    type="text"
                    value={domain}
                    onChange={e => setDomain(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && domain.trim() && mutate()}
                    placeholder="stripe.com"
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Company Name (optional)</label>
                  <input
                    type="text"
                    value={companyName}
                    onChange={e => setCompanyName(e.target.value)}
                    placeholder="Stripe"
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                </div>
              </div>
              {isError && <p className="text-sm text-red-600">{(error as Error).message}</p>}
            </div>
          )}

          {result && (
            <div className="space-y-4">
              <EnrichmentCard data={result} />
              <DomainContacts domain={result.domain} />
            </div>
          )}

          {isPending && (
            <div className="flex items-center gap-3 text-gray-500 text-sm py-4">
              <Loader2 size={18} className="animate-spin text-brand-500" />
              Enriching {domain}… this takes ~15 seconds
            </div>
          )}
        </div>

        <div className="flex items-center justify-between px-6 py-4 border-t border-gray-100 flex-shrink-0">
          {result ? (
            <button onClick={() => { setResult(null); setDomain(''); setCompanyName('') }} className="text-sm text-brand-600 hover:underline">
              Enrich another
            </button>
          ) : <span />}
          <div className="flex gap-2">
            <button onClick={onClose} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 text-gray-700">Close</button>
            {!result && (
              <button
                onClick={() => mutate()}
                disabled={isPending || !domain.trim()}
                className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isPending ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />}
                {isPending ? 'Enriching…' : 'Enrich'}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Bulk Modal ───────────────────────────────────────────────────────────────

function BulkModal({ onClose }: { onClose: () => void }) {
  const [domains, setDomains] = useState('')
  const [jobId, setJobId] = useState<string | null>(null)
  const [done, setDone] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const qc = useQueryClient()

  const { mutate, isPending } = useMutation({
    mutationFn: () => {
      const list = domains.split('\n').map(l => l.trim()).filter(Boolean).map(l => {
        const [domain, company_name] = l.split(',').map(s => s.trim())
        return { domain, ...(company_name ? { company_name } : {}) }
      })
      return api.enrichment.bulk(list)
    },
    onSuccess: (data) => setJobId(data.job_id),
  })

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const result = await api.enrichment.upload(file)
    if (result.job_id) setJobId(result.job_id)
  }

  const handleComplete = () => {
    setDone(true)
    qc.invalidateQueries({ queryKey: ['enrichments'] })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h3 className="text-lg font-semibold text-gray-900">Bulk Import</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={20} /></button>
        </div>

        <div className="p-6 space-y-5">
          {!jobId && (
            <>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Paste domains — one per line, optional company name after comma</label>
                <textarea
                  value={domains}
                  onChange={e => setDomains(e.target.value)}
                  rows={7}
                  placeholder={`stripe.com, Stripe\nlinear.app\nvercel.com, Vercel`}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
              <div className="relative">
                <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-gray-200" /></div>
                <div className="relative flex justify-center"><span className="bg-white px-2 text-xs text-gray-400">or upload a file</span></div>
              </div>
              <div
                className="border-2 border-dashed border-gray-200 rounded-lg p-6 text-center cursor-pointer hover:border-brand-300 hover:bg-brand-50 transition-colors"
                onClick={() => fileRef.current?.click()}
              >
                <Upload size={20} className="mx-auto text-gray-400 mb-1" />
                <p className="text-sm text-gray-600">CSV or YAML with <code className="text-xs bg-gray-100 px-1 rounded">domain</code> column</p>
                <input ref={fileRef} type="file" accept=".csv,.yaml,.yml" onChange={handleFile} className="hidden" />
              </div>
            </>
          )}

          {jobId && (
            <div className="space-y-3">
              <p className="text-sm font-medium text-gray-700">{done ? 'Enrichment complete!' : 'Enrichment in progress…'}</p>
              {!done && <JobPoller jobId={jobId} onComplete={handleComplete} onError={() => setDone(true)} />}
              {done && <p className="text-sm text-green-600">All domains enriched. Close to view results in the library.</p>}
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2 px-6 py-4 border-t border-gray-100">
          <button onClick={onClose} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 text-gray-700">
            {done ? 'Done' : 'Cancel'}
          </button>
          {!jobId && (
            <button
              onClick={() => mutate()}
              disabled={isPending || !domains.trim()}
              className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isPending ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />}
              Start Bulk Enrichment
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

function LibraryRow({ data }: { data: EnrichmentData }) {
  const [expanded, setExpanded] = useState(false)
  const location = [data.hq_city, data.hq_state, data.hq_country].filter(Boolean).join(', ')

  return (
    <Card>
      <button
        className="w-full text-left px-6 py-4 flex items-center justify-between hover:bg-gray-50 transition-colors rounded-xl"
        onClick={() => setExpanded(v => !v)}
      >
        <div className="flex items-center gap-4 min-w-0">
          <div className="min-w-0">
            <p className="font-medium text-gray-900">{data.company_name || data.domain}</p>
            <p className="text-xs text-gray-500 mt-0.5">
              {data.domain}
              {location ? ` · ${location}` : ''}
              {data.industry ? ` · ${data.industry}` : ''}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3 flex-shrink-0 ml-4">
          {data.employee_count_range && <span className="text-xs text-gray-400 hidden sm:block">{data.employee_count_range}</span>}
          {data.ai_insights?.growth_stage && <span className="text-xs text-gray-400 hidden sm:block">{data.ai_insights.growth_stage}</span>}
          <Badge label={data.data_quality} />
          <span className="text-gray-300 text-xs">{expanded ? '▲' : '▼'}</span>
        </div>
      </button>

      {expanded && (
        <div className="px-6 pb-6 space-y-4 border-t border-gray-100 pt-4">
          <EnrichmentCard data={data} />
          <DomainContacts domain={data.domain} />
        </div>
      )}
    </Card>
  )
}

export default function Enrichment() {
  const [search, setSearch] = useState('')
  const [showEnrichModal, setShowEnrichModal] = useState(false)
  const [showBulkModal, setShowBulkModal] = useState(false)

  const { data: enrichments = [], isLoading } = useQuery({
    queryKey: ['enrichments'],
    queryFn: () => api.enrichment.list(200),
  })

  const filtered = (enrichments as EnrichmentData[]).filter(e =>
    !search || (e.domain + (e.company_name || '') + (e.industry || '')).toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Enrichment</h2>
          <p className="text-gray-500 mt-1">Research companies before you reach out</p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {enrichments.length > 0 && (
            <a
              href={api.exports.enrichmentCsv()}
              download
              className="flex items-center gap-1.5 px-3 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 text-gray-600"
            >
              <Download size={14} /> Export
            </a>
          )}
          <button
            onClick={() => setShowBulkModal(true)}
            className="flex items-center gap-1.5 px-3 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 text-gray-700"
          >
            <Upload size={14} /> Bulk Import
          </button>
          <button
            onClick={() => setShowEnrichModal(true)}
            className="flex items-center gap-1.5 px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700"
          >
            <Search size={14} /> Enrich Domain
          </button>
        </div>
      </div>

      {/* Search */}
      {enrichments.length > 0 && (
        <div className="relative">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Filter by domain, company, or industry…"
            className="w-full pl-9 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>
      )}

      {/* Library */}
      {isLoading && <div className="py-16 text-center text-gray-400 text-sm">Loading…</div>}

      {!isLoading && enrichments.length === 0 && (
        <div className="py-20 text-center">
          <Search size={40} className="mx-auto text-gray-200 mb-4" />
          <p className="text-gray-500 font-medium">No enriched companies yet</p>
          <p className="text-gray-400 text-sm mt-1">Click "Enrich Domain" to research your first company</p>
          <button
            onClick={() => setShowEnrichModal(true)}
            className="mt-4 px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700"
          >
            Enrich a Domain
          </button>
        </div>
      )}

      {!isLoading && enrichments.length > 0 && filtered.length === 0 && (
        <div className="py-12 text-center text-gray-400 text-sm">No results match "{search}"</div>
      )}

      <div className="space-y-3">
        {filtered.map(e => <LibraryRow key={e.domain} data={e as EnrichmentData} />)}
      </div>

      {/* Modals */}
      {showEnrichModal && <EnrichModal onClose={() => setShowEnrichModal(false)} />}
      {showBulkModal && <BulkModal onClose={() => setShowBulkModal(false)} />}
    </div>
  )
}
