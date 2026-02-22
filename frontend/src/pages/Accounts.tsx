import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { Card } from '../components/Card'
import { Badge } from '../components/Badge'
import { Building2, Search } from 'lucide-react'

export default function Accounts() {
  const { data: accounts = [], isLoading } = useQuery({ queryKey: ['accounts'], queryFn: () => api.accounts.list(200) })
  const [search, setSearch] = useState('')
  const filtered = accounts.filter(a => !search || a.company_name.toLowerCase().includes(search.toLowerCase()) || a.domain.toLowerCase().includes(search.toLowerCase()))

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div><h2 className="text-2xl font-bold text-gray-900">Accounts</h2><p className="text-gray-500 mt-1">All companies across all campaigns</p></div>
      <div className="relative"><Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" /><input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search companies..." className="w-full pl-9 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" /></div>
      {isLoading ? <div className="text-center py-12 text-gray-400">Loading...</div> : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-xs text-gray-500 uppercase"><tr><th className="px-4 py-3 text-left">Company</th><th className="px-4 py-3 text-left">Domain</th><th className="px-4 py-3 text-left">Industry</th><th className="px-4 py-3 text-left">Size</th><th className="px-4 py-3 text-left">Status</th><th className="px-4 py-3 text-left">Enriched</th><th className="px-4 py-3 text-left">Campaign</th></tr></thead>
              <tbody className="divide-y divide-gray-100">
                {filtered.map(a => (
                  <tr key={a.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium"><Link to={`/accounts/${a.id}`} className="hover:text-brand-600 flex items-center gap-2"><Building2 size={14} className="text-gray-400" />{a.company_name}</Link></td>
                    <td className="px-4 py-3 text-gray-500 font-mono text-xs">{a.domain}</td>
                    <td className="px-4 py-3 text-gray-600">{a.industry || '-'}</td>
                    <td className="px-4 py-3 text-gray-600">{a.employee_count || '-'}</td>
                    <td className="px-4 py-3"><Badge label={a.status} /></td>
                    <td className="px-4 py-3">{a.has_enrichment ? <span className="text-green-600 text-xs">✓</span> : <span className="text-gray-300 text-xs">-</span>}</td>
                    <td className="px-4 py-3 text-gray-500 font-mono text-xs">{a.campaign_id}</td>
                  </tr>
                ))}
                {filtered.length === 0 && <tr><td colSpan={7} className="px-4 py-12 text-center text-gray-400">No accounts found</td></tr>}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  )
}
