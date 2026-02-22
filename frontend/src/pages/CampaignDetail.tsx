import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../api/client'
import { Card, CardHeader, CardBody } from '../components/Card'
import { Badge } from '../components/Badge'
import { ArrowLeft, Download, CheckSquare, Square } from 'lucide-react'

export default function CampaignDetail() {
  const { id } = useParams<{ id: string }>()
  const qc = useQueryClient()
  const [tab, setTab] = useState<'accounts' | 'contacts' | 'emails'>('accounts')
  const [selected, setSelected] = useState<Set<number>>(new Set())

  const { data: campaign } = useQuery({ queryKey: ['campaign', id], queryFn: () => api.campaigns.get(id!) })
  const { data: accounts = [] } = useQuery({ queryKey: ['campaign-accounts', id], queryFn: () => api.campaigns.getAccounts(id!), enabled: tab === 'accounts' })
  const { data: contacts = [] } = useQuery({ queryKey: ['campaign-contacts', id], queryFn: () => api.campaigns.getContacts(id!), enabled: tab === 'contacts' })
  const { data: emails = [] } = useQuery({ queryKey: ['campaign-emails', id], queryFn: () => api.campaigns.getEmails(id!), enabled: tab === 'emails' })

  const approveMut = useMutation({
    mutationFn: (ids: number[]) => {
      if (tab === 'accounts') return api.campaigns.reviewAccounts(id!, ids, [])
      if (tab === 'contacts') return api.campaigns.reviewContacts(id!, ids, [])
      return api.campaigns.reviewEmails(id!, ids, [])
    },
    onSuccess: () => { setSelected(new Set()); qc.invalidateQueries({ queryKey: [`campaign-${tab}`, id] }) },
  })

  const toggle = (itemId: number) => setSelected(prev => { const n = new Set(prev); n.has(itemId) ? n.delete(itemId) : n.add(itemId); return n })
  const selectAll = (items: { id: number }[]) => setSelected(new Set(items.map(i => i.id)))

  if (!campaign) return <div className="p-6 text-gray-400">Loading...</div>

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="flex items-center gap-4">
        <Link to="/campaigns" className="text-gray-400 hover:text-gray-600"><ArrowLeft size={20} /></Link>
        <div>
          <div className="flex items-center gap-3"><h2 className="text-2xl font-bold font-mono text-gray-900">{id}</h2><Badge label={campaign.current_stage.replace(/_/g, ' ')} /></div>
          <p className="text-gray-500 text-sm mt-1">{campaign.account_count} accounts · {campaign.contact_count} contacts · {campaign.approved_count} approved</p>
        </div>
        <div className="ml-auto">
          <a href={api.exports.campaignCsv(id!)} className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg text-sm text-gray-700 hover:bg-gray-50"><Download size={16} /> Export CSV</a>
        </div>
      </div>

      <div className="flex gap-1 bg-gray-100 p-1 rounded-lg w-fit">
        {(['accounts', 'contacts', 'emails'] as const).map(t => (
          <button key={t} onClick={() => { setTab(t); setSelected(new Set()) }} className={`px-4 py-1.5 rounded-md text-sm font-medium capitalize transition-colors ${tab === t ? 'bg-white shadow-sm text-gray-900' : 'text-gray-500 hover:text-gray-700'}`}>{t}</button>
        ))}
      </div>

      {selected.size > 0 && (
        <div className="flex items-center gap-3 p-3 bg-brand-50 border border-brand-200 rounded-lg">
          <span className="text-sm text-brand-700 font-medium">{selected.size} selected</span>
          <button onClick={() => approveMut.mutate([...selected])} className="px-3 py-1.5 bg-brand-500 text-white rounded text-sm hover:bg-brand-600">Approve Selected</button>
          <button onClick={() => setSelected(new Set())} className="text-sm text-gray-500 hover:text-gray-700">Clear</button>
        </div>
      )}

      {tab === 'accounts' && (
        <Card>
          <CardHeader><div className="flex items-center justify-between"><h3 className="font-semibold">Accounts ({accounts.length})</h3><button onClick={() => selectAll(accounts as any[])} className="text-sm text-brand-600 hover:underline">Select all</button></div></CardHeader>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-xs text-gray-500 uppercase"><tr><th className="px-4 py-3 w-8"></th><th className="px-4 py-3 text-left">Company</th><th className="px-4 py-3 text-left">Domain</th><th className="px-4 py-3 text-left">Industry</th><th className="px-4 py-3 text-left">Size</th><th className="px-4 py-3 text-left">Status</th><th className="px-4 py-3 text-left">Enriched</th></tr></thead>
              <tbody className="divide-y divide-gray-100">
                {(accounts as any[]).map(a => (
                  <tr key={a.id} className={`hover:bg-gray-50 cursor-pointer ${selected.has(a.id) ? 'bg-brand-50' : ''}`} onClick={() => toggle(a.id)}>
                    <td className="px-4 py-3">{selected.has(a.id) ? <CheckSquare size={16} className="text-brand-500" /> : <Square size={16} className="text-gray-300" />}</td>
                    <td className="px-4 py-3 font-medium"><Link to={`/accounts/${a.id}`} className="hover:text-brand-600" onClick={e => e.stopPropagation()}>{a.company_name}</Link></td>
                    <td className="px-4 py-3 text-gray-500 font-mono text-xs">{a.domain}</td>
                    <td className="px-4 py-3 text-gray-600">{a.industry || '-'}</td>
                    <td className="px-4 py-3 text-gray-600">{a.employee_count || '-'}</td>
                    <td className="px-4 py-3"><Badge label={a.status} /></td>
                    <td className="px-4 py-3">{a.has_enrichment ? <span className="text-green-600 text-xs font-medium">✓ Yes</span> : <span className="text-gray-300 text-xs">-</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {tab === 'contacts' && (
        <Card>
          <CardHeader><div className="flex items-center justify-between"><h3 className="font-semibold">Contacts ({contacts.length})</h3><button onClick={() => selectAll(contacts as any[])} className="text-sm text-brand-600 hover:underline">Select all</button></div></CardHeader>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-xs text-gray-500 uppercase"><tr><th className="px-4 py-3 w-8"></th><th className="px-4 py-3 text-left">Name</th><th className="px-4 py-3 text-left">Title</th><th className="px-4 py-3 text-left">Company</th><th className="px-4 py-3 text-left">Email</th><th className="px-4 py-3 text-left">Confidence</th><th className="px-4 py-3 text-left">Status</th></tr></thead>
              <tbody className="divide-y divide-gray-100">
                {(contacts as any[]).map(c => (
                  <tr key={c.id} className={`hover:bg-gray-50 cursor-pointer ${selected.has(c.id) ? 'bg-brand-50' : ''}`} onClick={() => toggle(c.id)}>
                    <td className="px-4 py-3">{selected.has(c.id) ? <CheckSquare size={16} className="text-brand-500" /> : <Square size={16} className="text-gray-300" />}</td>
                    <td className="px-4 py-3 font-medium"><Link to={`/contacts/${c.id}`} className="hover:text-brand-600" onClick={e => e.stopPropagation()}>{c.full_name}</Link></td>
                    <td className="px-4 py-3 text-gray-600">{c.title || '-'}</td>
                    <td className="px-4 py-3 text-gray-600">{c.company_name || '-'}</td>
                    <td className="px-4 py-3 text-gray-500 font-mono text-xs">{c.email || '-'}</td>
                    <td className="px-4 py-3">{c.email_confidence != null ? <div className="flex items-center gap-2"><div className="w-12 bg-gray-100 rounded-full h-1.5"><div className={`h-1.5 rounded-full ${c.email_confidence > 70 ? 'bg-green-500' : c.email_confidence > 40 ? 'bg-yellow-500' : 'bg-red-400'}`} style={{ width: `${c.email_confidence}%` }} /></div><span className="text-xs text-gray-500">{c.email_confidence}%</span></div> : '-'}</td>
                    <td className="px-4 py-3"><Badge label={c.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {tab === 'emails' && (
        <div className="space-y-3">
          <div className="flex justify-between"><p className="text-sm text-gray-500">{emails.length} drafts</p><button onClick={() => selectAll(emails as any[])} className="text-sm text-brand-600 hover:underline">Select all</button></div>
          {(emails as any[]).map(e => (
            <Card key={e.id} className={selected.has(e.id) ? 'ring-2 ring-brand-500' : ''}>
              <CardBody>
                <div className="flex items-start gap-3">
                  <button onClick={() => toggle(e.id)} className="mt-0.5">{selected.has(e.id) ? <CheckSquare size={18} className="text-brand-500" /> : <Square size={18} className="text-gray-300" />}</button>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-2"><div><p className="font-medium text-gray-900">{e.contact_name}</p><p className="text-xs text-gray-500">{e.contact_email} · {e.company_name}</p></div><Badge label={e.status} /></div>
                    <p className="text-sm font-medium text-gray-800 mb-2">Subject: {e.subject_line}</p>
                    <p className="text-sm text-gray-600 whitespace-pre-wrap line-clamp-4">{e.body}</p>
                    {e.personalization_hooks?.length > 0 && <div className="mt-2 flex flex-wrap gap-1">{e.personalization_hooks.map((h: string, i: number) => <span key={i} className="text-xs px-2 py-0.5 bg-purple-50 text-purple-700 rounded">{h}</span>)}</div>}
                  </div>
                </div>
              </CardBody>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
