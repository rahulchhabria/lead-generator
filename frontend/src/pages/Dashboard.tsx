import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { Card, CardBody } from '../components/Card'
import { Badge } from '../components/Badge'
import { Building2, Users, Megaphone, Search, ArrowRight } from 'lucide-react'

function StatCard({ label, value, icon: Icon, to, color }: { label: string; value: number; icon: React.ElementType; to: string; color: string }) {
  return (
    <Link to={to}>
      <Card className="hover:shadow-md transition-shadow">
        <CardBody className="flex items-center gap-4">
          <div className={`p-3 rounded-lg ${color}`}><Icon size={20} className="text-white" /></div>
          <div><p className="text-2xl font-bold text-gray-900">{value}</p><p className="text-sm text-gray-500">{label}</p></div>
        </CardBody>
      </Card>
    </Link>
  )
}

export default function Dashboard() {
  const { data: campaigns = [] } = useQuery({ queryKey: ['campaigns'], queryFn: api.campaigns.list })
  const { data: accounts = [] } = useQuery({ queryKey: ['accounts'], queryFn: () => api.accounts.list() })
  const { data: contacts = [] } = useQuery({ queryKey: ['contacts'], queryFn: () => api.contacts.list() })
  const { data: enrichments = [] } = useQuery({ queryKey: ['enrichments'], queryFn: () => api.enrichment.list() })
  const active = campaigns.filter(c => c.current_stage !== 'completed')

  return (
    <div className="p-6 space-y-8 max-w-7xl mx-auto">
      <div><h2 className="text-2xl font-bold text-gray-900">Dashboard</h2><p className="text-gray-500 mt-1">Your prospect intelligence overview</p></div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Campaigns" value={campaigns.length} icon={Megaphone} to="/campaigns" color="bg-brand-500" />
        <StatCard label="Enriched Accounts" value={enrichments.length} icon={Search} to="/enrichment" color="bg-purple-500" />
        <StatCard label="Accounts" value={accounts.length} icon={Building2} to="/accounts" color="bg-blue-500" />
        <StatCard label="Contacts" value={contacts.length} icon={Users} to="/contacts" color="bg-green-500" />
      </div>
      <div className="grid lg:grid-cols-2 gap-6">
        <Card>
          <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
            <h3 className="font-semibold text-gray-900">Active Campaigns</h3>
            <Link to="/campaigns" className="text-sm text-brand-600 hover:underline flex items-center gap-1">View all <ArrowRight size={14} /></Link>
          </div>
          <div className="divide-y divide-gray-100">
            {active.length === 0 && <div className="px-6 py-8 text-center text-gray-400 text-sm">No active campaigns. <Link to="/campaigns" className="text-brand-600 hover:underline">Create one</Link></div>}
            {active.slice(0, 5).map(c => (
              <Link key={c.id} to={`/campaigns/${c.id}`} className="flex items-center justify-between px-6 py-3 hover:bg-gray-50">
                <div><p className="text-sm font-medium font-mono">{c.id}</p><p className="text-xs text-gray-500">{c.account_count} accounts · {c.contact_count} contacts</p></div>
                <Badge label={c.current_stage.replace(/_/g, ' ')} />
              </Link>
            ))}
          </div>
        </Card>
        <Card>
          <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
            <h3 className="font-semibold text-gray-900">Recent Enrichments</h3>
            <Link to="/enrichment" className="text-sm text-brand-600 hover:underline flex items-center gap-1">View all <ArrowRight size={14} /></Link>
          </div>
          <div className="divide-y divide-gray-100">
            {enrichments.length === 0 && <div className="px-6 py-8 text-center text-gray-400 text-sm">No enriched companies yet. <Link to="/enrichment" className="text-brand-600 hover:underline">Enrich a domain</Link></div>}
            {(enrichments as any[]).slice(0, 5).map(e => (
              <div key={e.domain} className="flex items-center justify-between px-6 py-3">
                <div><p className="text-sm font-medium">{e.company_name || e.domain}</p><p className="text-xs text-gray-500">{e.domain} · {e.industry || 'Unknown'}</p></div>
                <Badge label={e.data_quality} />
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  )
}
