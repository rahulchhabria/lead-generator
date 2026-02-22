import { EnrichmentData } from '../api/client'
import { Badge } from './Badge'
import { Card, CardHeader, CardBody } from './Card'
import { ExternalLink } from 'lucide-react'

export function EnrichmentCard({ data }: { data: EnrichmentData }) {
  const techList = data.technographic?.all_technologies?.slice(0, 14) || []
  const location = [data.hq_city, data.hq_state, data.hq_country].filter(Boolean).join(', ')

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-gray-900">Company Overview</h3>
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-500">Score: {data.confidence_score}/100</span>
              <Badge label={data.data_quality} />
            </div>
          </div>
        </CardHeader>
        <CardBody>
          <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3 text-sm">
            {data.employee_count_range && <div><dt className="text-xs text-gray-500">Employees</dt><dd className="font-medium mt-0.5">{data.employee_count_range}</dd></div>}
            {data.founded_year && <div><dt className="text-xs text-gray-500">Founded</dt><dd className="font-medium mt-0.5">{data.founded_year}</dd></div>}
            {location && <div><dt className="text-xs text-gray-500">HQ</dt><dd className="font-medium mt-0.5">{location}</dd></div>}
            {data.industry && <div><dt className="text-xs text-gray-500">Industry</dt><dd className="font-medium mt-0.5">{data.industry}</dd></div>}
            {data.total_funding_raised && <div><dt className="text-xs text-gray-500">Funding</dt><dd className="font-medium mt-0.5">{data.total_funding_raised}</dd></div>}
            {data.ai_insights?.growth_stage && <div><dt className="text-xs text-gray-500">Stage</dt><dd className="font-medium mt-0.5">{data.ai_insights.growth_stage}</dd></div>}
            {data.ceo && <div><dt className="text-xs text-gray-500">CEO</dt><dd className="font-medium mt-0.5">{data.ceo.name}</dd></div>}
            {data.hiring && <div><dt className="text-xs text-gray-500">Open Roles</dt><dd className="font-medium mt-0.5">{data.hiring.open_positions}</dd></div>}
          </dl>
          {data.description && <p className="mt-4 text-sm text-gray-700 leading-relaxed">{data.description}</p>}
          <div className="mt-3 flex gap-3 flex-wrap">
            {data.linkedin_url && <a href={data.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-xs text-brand-600 hover:underline flex items-center gap-1">LinkedIn <ExternalLink size={10} /></a>}
            {data.github_url && <a href={data.github_url} target="_blank" rel="noopener noreferrer" className="text-xs text-brand-600 hover:underline flex items-center gap-1">GitHub <ExternalLink size={10} /></a>}
          </div>
        </CardBody>
      </Card>

      {techList.length > 0 && (
        <Card>
          <CardHeader><h3 className="font-semibold text-sm">Tech Stack ({data.technographic?.all_technologies?.length || 0})</h3></CardHeader>
          <CardBody>
            <div className="flex flex-wrap gap-1.5">
              {techList.map(t => <span key={t} className="px-2 py-1 bg-gray-100 rounded text-xs text-gray-700">{t}</span>)}
              {(data.technographic?.all_technologies?.length || 0) > 14 && <span className="px-2 py-1 bg-gray-100 rounded text-xs text-gray-500">+{(data.technographic?.all_technologies?.length || 0) - 14} more</span>}
            </div>
          </CardBody>
        </Card>
      )}

      {data.hiring && data.hiring.open_positions > 0 && data.hiring.top_skills.length > 0 && (
        <Card>
          <CardHeader><h3 className="font-semibold text-sm">Hiring — {data.hiring.open_positions} open roles</h3></CardHeader>
          <CardBody>
            <p className="text-xs text-gray-500 mb-2">Top Skills</p>
            <div className="flex flex-wrap gap-1.5">
              {data.hiring.top_skills.map(s => <span key={s} className="px-2 py-1 bg-blue-50 text-blue-700 rounded text-xs">{s}</span>)}
            </div>
          </CardBody>
        </Card>
      )}

      {data.ai_insights?.recent_news && data.ai_insights.recent_news.length > 0 && (
        <Card>
          <CardHeader><h3 className="font-semibold text-sm">Recent News</h3></CardHeader>
          <CardBody>
            <ul className="space-y-2">
              {data.ai_insights.recent_news.map((n, i) => <li key={i} className="text-sm text-gray-700 flex gap-2"><span className="text-gray-300">•</span><span>{n}</span></li>)}
            </ul>
          </CardBody>
        </Card>
      )}

      {data.ai_insights?.key_differentiators && data.ai_insights.key_differentiators.length > 0 && (
        <Card>
          <CardHeader><h3 className="font-semibold text-sm">Key Differentiators</h3></CardHeader>
          <CardBody>
            <ul className="space-y-1">
              {data.ai_insights.key_differentiators.map((d, i) => <li key={i} className="text-sm text-gray-700 flex gap-2"><span className="text-green-500">✓</span><span>{d}</span></li>)}
            </ul>
          </CardBody>
        </Card>
      )}
    </div>
  )
}
