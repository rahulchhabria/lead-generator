import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { Card, CardHeader, CardBody } from '../components/Card'
import { Badge } from '../components/Badge'
import { EnrichmentCard } from '../components/EnrichmentCard'
import { ArrowLeft } from 'lucide-react'

export default function ContactDetail() {
  const { id } = useParams<{ id: string }>()
  const { data: contact } = useQuery({ queryKey: ['contact', id], queryFn: () => api.contacts.get(Number(id)) })
  if (!contact) return <div className="p-6 text-gray-400">Loading...</div>

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="flex items-center gap-4">
        <Link to="/contacts" className="text-gray-400 hover:text-gray-600"><ArrowLeft size={20} /></Link>
        <div>
          <div className="flex items-center gap-3"><h2 className="text-2xl font-bold text-gray-900">{contact.full_name}</h2><Badge label={contact.status} /></div>
          <p className="text-gray-500 text-sm mt-1">{contact.title}{contact.company?.name ? ` at ${contact.company.name}` : ''}</p>
        </div>
      </div>
      <div className="grid lg:grid-cols-3 gap-6">
        <div className="space-y-4">
          <Card>
            <CardHeader><h3 className="font-semibold">Contact Info</h3></CardHeader>
            <CardBody className="space-y-3 text-sm">
              {contact.email && <div><dt className="text-xs text-gray-500">Email</dt><dd className="font-mono text-xs mt-0.5">{contact.email}</dd><dd className="text-xs text-gray-400 mt-0.5">Confidence: {contact.email_confidence ?? '-'}% · {contact.email_verified ? '✓ Verified' : 'Unverified'}</dd></div>}
              {contact.linkedin_url && <div><dt className="text-xs text-gray-500">LinkedIn</dt><dd className="mt-0.5"><a href={contact.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-brand-600 hover:underline text-xs">View Profile</a></dd></div>}
              {contact.company?.name && <div><dt className="text-xs text-gray-500">Company</dt><dd className="mt-0.5">{contact.company.name}</dd></div>}
            </CardBody>
          </Card>
          {contact.dossier && (
            <Card>
              <CardHeader><h3 className="font-semibold">Research Dossier</h3></CardHeader>
              <CardBody className="space-y-3 text-sm">
                {contact.dossier.github_username && <div><dt className="text-xs text-gray-500">GitHub</dt><dd className="mt-0.5"><a href={`https://github.com/${contact.dossier.github_username}`} target="_blank" rel="noopener noreferrer" className="text-brand-600 hover:underline text-xs">@{contact.dossier.github_username}</a></dd>{contact.dossier.github_languages.length > 0 && <div className="flex flex-wrap gap-1 mt-1">{contact.dossier.github_languages.slice(0, 5).map(l => <span key={l} className="px-1.5 py-0.5 bg-gray-100 rounded text-xs">{l}</span>)}</div>}</div>}
                {contact.dossier.interests.length > 0 && <div><dt className="text-xs text-gray-500 mb-1">Interests</dt><div className="flex flex-wrap gap-1">{contact.dossier.interests.map(i => <span key={i} className="px-1.5 py-0.5 bg-blue-50 text-blue-700 rounded text-xs">{i}</span>)}</div></div>}
                {contact.dossier.personal_details.length > 0 && <div><dt className="text-xs text-gray-500 mb-1">Details</dt><ul className="space-y-1">{contact.dossier.personal_details.map((d, i) => <li key={i} className="text-xs text-gray-600">• {d}</li>)}</ul></div>}
              </CardBody>
            </Card>
          )}
        </div>
        <div className="lg:col-span-2 space-y-4">
          {contact.emails.length > 0 && (
            <Card>
              <CardHeader><h3 className="font-semibold">Draft Emails ({contact.emails.length})</h3></CardHeader>
              <div className="divide-y divide-gray-100">
                {contact.emails.map(e => (
                  <div key={e.id} className="px-6 py-4">
                    <div className="flex items-center justify-between mb-2"><p className="text-sm font-medium text-gray-900">Subject: {e.subject_line}</p><Badge label={e.status} /></div>
                    <p className="text-sm text-gray-700 whitespace-pre-wrap">{e.body}</p>
                    {e.personalization_hooks?.length > 0 && <div className="mt-3 flex flex-wrap gap-1">{e.personalization_hooks.map((h, i) => <span key={i} className="text-xs px-2 py-0.5 bg-purple-50 text-purple-700 rounded">{h}</span>)}</div>}
                  </div>
                ))}
              </div>
            </Card>
          )}
          {contact.account_enrichment && <div><h3 className="text-sm font-semibold text-gray-700 mb-3">Account Intelligence</h3><EnrichmentCard data={contact.account_enrichment} /></div>}
        </div>
      </div>
    </div>
  )
}
