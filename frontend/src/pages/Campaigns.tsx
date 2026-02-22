import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { Card, CardBody } from '../components/Card'
import { Badge } from '../components/Badge'
import { JobPoller } from '../components/JobPoller'
import { Plus, Megaphone, ArrowRight, Building2, Users, CheckCircle } from 'lucide-react'

export default function Campaigns() {
  const qc = useQueryClient()
  const { data: campaigns = [], isLoading } = useQuery({ queryKey: ['campaigns'], queryFn: api.campaigns.list })
  const [showCreate, setShowCreate] = useState(false)
  const [createJobId, setCreateJobId] = useState<string | null>(null)
  const [form, setForm] = useState({ mode: 'icp' as 'icp' | 'domains', icpDescription: '', targetRoles: 'CTO, VP Engineering', companySize: '50-500 employees', industries: 'SaaS, FinTech', domains: '', senderName: '', senderCompany: '', valueProposition: '' })

  const createMut = useMutation({
    mutationFn: () => {
      const body: any = { config: {} }
      if (form.senderName) body.config.sender_name = form.senderName
      if (form.senderCompany) body.config.sender_company = form.senderCompany
      if (form.valueProposition) body.config.value_proposition = form.valueProposition
      if (form.mode === 'icp') {
        body.icp = { description: form.icpDescription, target_roles: form.targetRoles.split(',').map((s: string) => s.trim()).filter(Boolean), company_size: form.companySize, industries: form.industries.split(',').map((s: string) => s.trim()).filter(Boolean) }
      } else {
        body.domains = form.domains.split('\n').map((d: string) => ({ domain: d.trim() })).filter((d: any) => d.domain)
        body.target_roles = form.targetRoles.split(',').map((s: string) => s.trim()).filter(Boolean)
      }
      return api.campaigns.create(body)
    },
    onSuccess: (data) => { setCreateJobId(data.job_id); qc.invalidateQueries({ queryKey: ['campaigns'] }) },
  })

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div><h2 className="text-2xl font-bold text-gray-900">Campaigns</h2><p className="text-gray-500 mt-1">End-to-end lead generation pipelines</p></div>
        <button onClick={() => setShowCreate(!showCreate)} className="flex items-center gap-2 px-4 py-2 bg-brand-500 text-white rounded-lg text-sm font-medium hover:bg-brand-600"><Plus size={16} /> New Campaign</button>
      </div>

      {showCreate && (
        <Card>
          <div className="px-6 py-4 border-b border-gray-100"><h3 className="font-semibold">Create Campaign</h3></div>
          <CardBody className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Start with</label>
              <div className="flex gap-2">
                {(['icp', 'domains'] as const).map(m => (
                  <button key={m} onClick={() => setForm(f => ({ ...f, mode: m }))}
                    className={`px-4 py-2 rounded-lg text-sm font-medium border transition-colors ${form.mode === m ? 'bg-brand-500 text-white border-brand-500' : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'}`}>
                    {m === 'icp' ? 'ICP (AI Discovery)' : 'Domain List'}
                  </button>
                ))}
              </div>
            </div>
            <div className="grid sm:grid-cols-2 gap-4">
              {form.mode === 'icp' && (
                <div className="sm:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-1">ICP Description *</label>
                  <textarea value={form.icpDescription} rows={3} onChange={e => setForm(f => ({ ...f, icpDescription: e.target.value }))}
                    placeholder="B2B SaaS companies with 50-500 engineers building developer tools..."
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                </div>
              )}
              {form.mode === 'domains' && (
                <div className="sm:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-1">Domains (one per line) *</label>
                  <textarea value={form.domains} rows={5} onChange={e => setForm(f => ({ ...f, domains: e.target.value }))}
                    placeholder={"stripe.com\nnotion.so\nlinear.app"}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 font-mono" />
                </div>
              )}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Target Roles</label>
                <input value={form.targetRoles} onChange={e => setForm(f => ({ ...f, targetRoles: e.target.value }))} className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
              </div>
              {form.mode === 'icp' && (
                <>
                  <div><label className="block text-sm font-medium text-gray-700 mb-1">Company Size</label><input value={form.companySize} onChange={e => setForm(f => ({ ...f, companySize: e.target.value }))} className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" /></div>
                  <div><label className="block text-sm font-medium text-gray-700 mb-1">Industries</label><input value={form.industries} onChange={e => setForm(f => ({ ...f, industries: e.target.value }))} className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" /></div>
                </>
              )}
              <div><label className="block text-sm font-medium text-gray-700 mb-1">Your Name</label><input value={form.senderName} onChange={e => setForm(f => ({ ...f, senderName: e.target.value }))} placeholder="Jane Smith" className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" /></div>
              <div><label className="block text-sm font-medium text-gray-700 mb-1">Your Company</label><input value={form.senderCompany} onChange={e => setForm(f => ({ ...f, senderCompany: e.target.value }))} placeholder="Acme Inc" className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" /></div>
              <div className="sm:col-span-2"><label className="block text-sm font-medium text-gray-700 mb-1">Value Proposition</label><input value={form.valueProposition} onChange={e => setForm(f => ({ ...f, valueProposition: e.target.value }))} placeholder="We help engineering teams ship 2x faster" className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" /></div>
            </div>
            <div className="flex gap-3">
              <button onClick={() => createMut.mutate()} disabled={createMut.isPending} className="px-6 py-2 bg-brand-500 text-white rounded-lg text-sm font-medium hover:bg-brand-600 disabled:opacity-50">{createMut.isPending ? 'Starting...' : 'Start Campaign'}</button>
              <button onClick={() => setShowCreate(false)} className="px-6 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-200">Cancel</button>
            </div>
            {createMut.isError && <p className="text-sm text-red-600">{(createMut.error as Error).message}</p>}
            {createJobId && <div className="mt-4"><JobPoller jobId={createJobId} onComplete={() => qc.invalidateQueries({ queryKey: ['campaigns'] })} /></div>}
          </CardBody>
        </Card>
      )}

      {isLoading ? <div className="text-center py-12 text-gray-400">Loading...</div> : campaigns.length === 0 ? (
        <Card><CardBody className="py-16 text-center"><Megaphone size={48} className="mx-auto text-gray-300 mb-4" /><p className="text-gray-500">No campaigns yet. Create your first one.</p></CardBody></Card>
      ) : (
        <div className="space-y-3">
          {campaigns.map(c => (
            <Link key={c.id} to={`/campaigns/${c.id}`}>
              <Card className="hover:shadow-md transition-shadow">
                <CardBody className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div>
                      <div className="flex items-center gap-2"><p className="font-medium font-mono text-gray-900">{c.id}</p><Badge label={c.current_stage.replace(/_/g, ' ')} /></div>
                      <div className="flex items-center gap-4 mt-1 text-xs text-gray-500">
                        <span className="flex items-center gap-1"><Building2 size={11} /> {c.account_count} accounts</span>
                        <span className="flex items-center gap-1"><Users size={11} /> {c.contact_count} contacts</span>
                        <span className="flex items-center gap-1"><CheckCircle size={11} /> {c.approved_count} approved</span>
                      </div>
                    </div>
                  </div>
                  <ArrowRight size={18} className="text-gray-400" />
                </CardBody>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
