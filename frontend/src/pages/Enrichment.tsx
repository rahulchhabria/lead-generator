import { useState, useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, EnrichmentData } from '../api/client'
import { Card, CardHeader, CardBody } from '../components/Card'
import { Badge } from '../components/Badge'
import { EnrichmentCard } from '../components/EnrichmentCard'
import { JobPoller } from '../components/JobPoller'
import { Search, Upload, Download, RefreshCw, Building2 } from 'lucide-react'

export default function Enrichment() {
  const qc = useQueryClient()
  const [domain, setDomain] = useState('')
  const [companyName, setCompanyName] = useState('')
  const [activeResult, setActiveResult] = useState<EnrichmentData | null>(null)
  const [bulkJobId, setBulkJobId] = useState<string | null>(null)
  const [tab, setTab] = useState<'single' | 'bulk' | 'library'>('single')
  const fileRef = useRef<HTMLInputElement>(null)

  const { data: enrichments = [], refetch: refetchList } = useQuery({ queryKey: ['enrichments'], queryFn: () => api.enrichment.list(100) })

  const enrichMut = useMutation({
    mutationFn: () => api.enrichment.single(domain.trim(), companyName.trim() || undefined),
    onSuccess: (data) => { setActiveResult(data); qc.invalidateQueries({ queryKey: ['enrichments'] }) },
  })

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]; if (!file) return
    const result = await api.enrichment.upload(file)
    if (result.job_id) { setBulkJobId(result.job_id); setTab('bulk') }
  }

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div><h2 className="text-2xl font-bold text-gray-900">Enrichment</h2><p className="text-gray-500 mt-1">Research companies before you reach out</p></div>
        <a href={api.exports.enrichmentCsv()} className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg text-sm text-gray-700 hover:bg-gray-50"><Download size={16} /> Export All</a>
      </div>

      <div className="flex gap-1 bg-gray-100 p-1 rounded-lg w-fit">
        {(['single', 'bulk', 'library'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)} className={`px-4 py-1.5 rounded-md text-sm font-medium capitalize transition-colors ${tab === t ? 'bg-white shadow-sm text-gray-900' : 'text-gray-500 hover:text-gray-700'}`}>
            {t === 'library' ? `Library (${enrichments.length})` : t}
          </button>
        ))}
      </div>

      {tab === 'single' && (
        <div className="grid lg:grid-cols-5 gap-6">
          <div className="lg:col-span-2 space-y-4">
            <Card>
              <CardHeader><h3 className="font-semibold">Enrich a Domain</h3></CardHeader>
              <CardBody className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Domain *</label>
                  <input value={domain} onChange={e => setDomain(e.target.value)} placeholder="stripe.com"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                    onKeyDown={e => e.key === 'Enter' && domain && enrichMut.mutate()} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Company Name (optional)</label>
                  <input value={companyName} onChange={e => setCompanyName(e.target.value)} placeholder="Stripe"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                </div>
                <button onClick={() => enrichMut.mutate()} disabled={!domain || enrichMut.isPending}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-brand-500 text-white rounded-lg text-sm font-medium hover:bg-brand-600 disabled:opacity-50">
                  {enrichMut.isPending ? <><RefreshCw size={16} className="animate-spin" /> Enriching...</> : <><Search size={16} /> Enrich Domain</>}
                </button>
                {enrichMut.isError && <p className="text-sm text-red-600">{(enrichMut.error as Error).message}</p>}
              </CardBody>
            </Card>
            {enrichments.length > 0 && (
              <Card>
                <CardHeader><h3 className="font-semibold text-sm">Recent</h3></CardHeader>
                <div className="divide-y divide-gray-100">
                  {(enrichments as any[]).slice(0, 8).map(e => (
                    <button key={e.domain} onClick={() => setActiveResult(e)} className="w-full flex items-center justify-between px-4 py-2.5 text-left hover:bg-gray-50">
                      <div><p className="text-sm font-medium">{e.company_name || e.domain}</p><p className="text-xs text-gray-500">{e.domain}</p></div>
                      <Badge label={e.data_quality} />
                    </button>
                  ))}
                </div>
              </Card>
            )}
          </div>
          <div className="lg:col-span-3">
            {activeResult ? <EnrichmentCard data={activeResult} /> : (
              <Card className="h-64 flex items-center justify-center">
                <div className="text-center text-gray-400"><Building2 size={48} className="mx-auto mb-3 opacity-30" /><p className="text-sm">Enter a domain to see enrichment data</p></div>
              </Card>
            )}
          </div>
        </div>
      )}

      {tab === 'bulk' && (
        <div className="space-y-6">
          <Card>
            <CardHeader><h3 className="font-semibold">Bulk Domain Enrichment</h3></CardHeader>
            <CardBody className="space-y-4">
              <p className="text-sm text-gray-600">Upload a CSV or YAML file with domains to enrich in bulk.</p>
              <div className="border-2 border-dashed border-gray-200 rounded-lg p-8 text-center">
                <Upload size={32} className="mx-auto text-gray-400 mb-3" />
                <p className="text-sm text-gray-600 mb-2">Drag & drop or click to upload</p>
                <p className="text-xs text-gray-400 mb-4">CSV (domain, company_name columns) or YAML</p>
                <button onClick={() => fileRef.current?.click()} className="px-4 py-2 bg-brand-500 text-white rounded-lg text-sm hover:bg-brand-600">Choose File</button>
                <input ref={fileRef} type="file" accept=".csv,.yaml,.yml" className="hidden" onChange={handleUpload} />
              </div>
              <div><p className="text-xs text-gray-500 font-medium mb-1">CSV Format:</p><pre className="text-xs bg-gray-50 p-3 rounded text-gray-600">{"domain,company_name\nstripe.com,Stripe\nnotion.so,Notion"}</pre></div>
            </CardBody>
          </Card>
          {bulkJobId && (
            <Card>
              <CardHeader><h3 className="font-semibold">Progress</h3></CardHeader>
              <CardBody><JobPoller jobId={bulkJobId} onComplete={() => { refetchList(); setBulkJobId(null) }} /></CardBody>
            </Card>
          )}
        </div>
      )}

      {tab === 'library' && (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {(enrichments as any[]).length === 0 && (
            <div className="col-span-full text-center py-12 text-gray-400"><Search size={48} className="mx-auto mb-3 opacity-30" /><p>No enriched companies yet.</p></div>
          )}
          {(enrichments as any[]).map(e => (
            <Card key={e.domain} className="hover:shadow-md transition-shadow" onClick={() => { setActiveResult(e); setTab('single') }}>
              <CardBody>
                <div className="flex items-start justify-between mb-2">
                  <div><p className="font-medium">{e.company_name || e.domain}</p><p className="text-xs text-gray-500">{e.domain}</p></div>
                  <Badge label={e.data_quality} />
                </div>
                {e.description && <p className="text-xs text-gray-600 line-clamp-2 mb-3">{e.description}</p>}
                <div className="flex flex-wrap gap-2 text-xs text-gray-500">
                  {e.employee_count_range && <span>👥 {e.employee_count_range}</span>}
                  {e.industry && <span>🏭 {e.industry}</span>}
                  {e.total_funding_raised && <span>💰 {e.total_funding_raised}</span>}
                </div>
              </CardBody>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
