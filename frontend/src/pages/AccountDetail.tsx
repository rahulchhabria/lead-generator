import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../api/client'
import { Card, CardHeader, CardBody } from '../components/Card'
import { Badge } from '../components/Badge'
import { EnrichmentCard } from '../components/EnrichmentCard'
import { JobPoller } from '../components/JobPoller'
import { ArrowLeft, RefreshCw } from 'lucide-react'

export default function AccountDetail() {
  const { id } = useParams<{ id: string }>()
  const [enrichJobId, setEnrichJobId] = useState<string | null>(null)
  const { data: account, refetch } = useQuery({ queryKey: ['account', id], queryFn: () => api.accounts.get(Number(id)) })
  const enrichMut = useMutation({ mutationFn: () => api.accounts.enrich(Number(id)), onSuccess: (data) => setEnrichJobId(data.job_id) })

  if (!account) return <div className="p-6 text-gray-400">Loading...</div>

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="flex items-center gap-4">
        <Link to="/accounts" className="text-gray-400 hover:text-gray-600"><ArrowLeft size={20} /></Link>
        <div><div className="flex items-center gap-3"><h2 className="text-2xl font-bold text-gray-900">{account.company_name}</h2><Badge label={account.status} /></div><p className="text-gray-500 text-sm mt-1">{account.domain}</p></div>
        <button onClick={() => enrichMut.mutate()} disabled={enrichMut.isPending} className="ml-auto flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg text-sm text-gray-700 hover:bg-gray-50">
          <RefreshCw size={16} className={enrichMut.isPending ? 'animate-spin' : ''} />{account.enrichment ? 'Re-enrich' : 'Enrich'}
        </button>
      </div>
      {enrichJobId && <Card><CardBody><JobPoller jobId={enrichJobId} onComplete={() => { refetch(); setEnrichJobId(null) }} /></CardBody></Card>}
      <div className="grid lg:grid-cols-3 gap-6">
        <div className="space-y-4">
          <Card>
            <CardHeader><h3 className="font-semibold">Account Info</h3></CardHeader>
            <CardBody>
              <dl className="space-y-3 text-sm">
                <div><dt className="text-xs text-gray-500">Domain</dt><dd className="font-mono mt-0.5">{account.domain}</dd></div>
                <div><dt className="text-xs text-gray-500">Industry</dt><dd className="mt-0.5">{account.industry || '-'}</dd></div>
                <div><dt className="text-xs text-gray-500">Size</dt><dd className="mt-0.5">{account.employee_count || '-'}</dd></div>
                <div><dt className="text-xs text-gray-500">Location</dt><dd className="mt-0.5">{account.location || '-'}</dd></div>
                <div><dt className="text-xs text-gray-500">Source</dt><dd className="mt-0.5"><Badge label={account.source} /></dd></div>
                <div><dt className="text-xs text-gray-500">Campaign</dt><dd className="mt-0.5"><Link to={`/campaigns/${account.campaign_id}`} className="text-brand-600 hover:underline font-mono text-xs">{account.campaign_id}</Link></dd></div>
              </dl>
              {account.description && <p className="mt-4 text-sm text-gray-700 border-t border-gray-100 pt-4 leading-relaxed">{account.description}</p>}
              {account.relevance_reasoning && <div className="mt-3 p-3 bg-blue-50 rounded-lg"><p className="text-xs text-blue-700">{account.relevance_reasoning}</p></div>}
            </CardBody>
          </Card>
          <Card>
            <CardHeader><h3 className="font-semibold">Contacts ({account.contacts?.length || 0})</h3></CardHeader>
            <div className="divide-y divide-gray-100">
              {account.contacts?.length === 0 && <div className="px-4 py-6 text-sm text-gray-400 text-center">No contacts yet</div>}
              {account.contacts?.map(c => (
                <Link key={c.id} to={`/contacts/${c.id}`} className="flex items-center justify-between px-4 py-3 hover:bg-gray-50">
                  <div><p className="text-sm font-medium">{c.full_name}</p><p className="text-xs text-gray-500">{c.title}</p>{c.email && <p className="text-xs text-gray-400 font-mono">{c.email}</p>}</div>
                  <Badge label={c.status} />
                </Link>
              ))}
            </div>
          </Card>
        </div>
        <div className="lg:col-span-2">
          {account.enrichment ? <EnrichmentCard data={account.enrichment} /> : (
            <Card className="h-64 flex items-center justify-center">
              <div className="text-center text-gray-400"><p className="text-sm mb-3">No enrichment data yet.</p><button onClick={() => enrichMut.mutate()} className="px-4 py-2 bg-brand-500 text-white rounded-lg text-sm hover:bg-brand-600">Enrich This Account</button></div>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
