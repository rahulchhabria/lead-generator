import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { Card } from '../components/Card'
import { Badge } from '../components/Badge'
import { Users, Search } from 'lucide-react'

export default function Contacts() {
  const { data: contacts = [], isLoading } = useQuery({ queryKey: ['contacts'], queryFn: () => api.contacts.list(200) })
  const [search, setSearch] = useState('')
  const filtered = contacts.filter(c => !search || c.full_name.toLowerCase().includes(search.toLowerCase()) || c.email?.toLowerCase().includes(search.toLowerCase()) || c.company_name?.toLowerCase().includes(search.toLowerCase()))

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div><h2 className="text-2xl font-bold text-gray-900">Contacts</h2><p className="text-gray-500 mt-1">All contacts across all campaigns</p></div>
      <div className="relative"><Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" /><input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search by name, email, or company..." className="w-full pl-9 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" /></div>
      {isLoading ? <div className="text-center py-12 text-gray-400">Loading...</div> : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-xs text-gray-500 uppercase"><tr><th className="px-4 py-3 text-left">Name</th><th className="px-4 py-3 text-left">Title</th><th className="px-4 py-3 text-left">Company</th><th className="px-4 py-3 text-left">Email</th><th className="px-4 py-3 text-left">Conf.</th><th className="px-4 py-3 text-left">Verified</th><th className="px-4 py-3 text-left">Status</th></tr></thead>
              <tbody className="divide-y divide-gray-100">
                {filtered.map(c => (
                  <tr key={c.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium"><Link to={`/contacts/${c.id}`} className="hover:text-brand-600 flex items-center gap-2"><Users size={14} className="text-gray-400" />{c.full_name}</Link></td>
                    <td className="px-4 py-3 text-gray-600">{c.title || '-'}</td>
                    <td className="px-4 py-3 text-gray-600">{c.company_name || '-'}</td>
                    <td className="px-4 py-3 text-gray-500 font-mono text-xs">{c.email || '-'}</td>
                    <td className="px-4 py-3 text-gray-600">{c.email_confidence != null ? `${c.email_confidence}%` : '-'}</td>
                    <td className="px-4 py-3">{c.email_verified ? <span className="text-green-600 text-xs">✓</span> : <span className="text-gray-300 text-xs">-</span>}</td>
                    <td className="px-4 py-3"><Badge label={c.status} /></td>
                  </tr>
                ))}
                {filtered.length === 0 && <tr><td colSpan={7} className="px-4 py-12 text-center text-gray-400">No contacts found</td></tr>}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  )
}
