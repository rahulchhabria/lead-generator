import clsx from 'clsx'

const variants: Record<string, string> = {
  discovered: 'bg-blue-100 text-blue-700', approved: 'bg-green-100 text-green-700',
  rejected: 'bg-red-100 text-red-700', contact_found: 'bg-purple-100 text-purple-700',
  contact_approved: 'bg-green-100 text-green-700', researched: 'bg-indigo-100 text-indigo-700',
  email_drafted: 'bg-yellow-100 text-yellow-700', email_approved: 'bg-emerald-100 text-emerald-700',
  failed: 'bg-red-100 text-red-700', completed: 'bg-emerald-100 text-emerald-700',
  high: 'bg-green-100 text-green-700', medium: 'bg-yellow-100 text-yellow-700',
  low: 'bg-red-100 text-red-700', running: 'bg-blue-100 text-blue-700',
  pending: 'bg-gray-100 text-gray-600', success: 'bg-green-100 text-green-700',
  error: 'bg-red-100 text-red-700', discovery: 'bg-blue-100 text-blue-700',
  discovery_review: 'bg-blue-100 text-blue-700', contact_finding: 'bg-purple-100 text-purple-700',
  contact_review: 'bg-purple-100 text-purple-700', research: 'bg-indigo-100 text-indigo-700',
  research_review: 'bg-indigo-100 text-indigo-700', email_composition: 'bg-yellow-100 text-yellow-700',
  email_review: 'bg-yellow-100 text-yellow-700', export: 'bg-emerald-100 text-emerald-700',
}

export function Badge({ label, className }: { label: string; className?: string }) {
  const key = label?.toLowerCase().replace(/\s/g, '_')
  return (
    <span className={clsx('inline-flex items-center px-2 py-0.5 rounded text-xs font-medium', variants[key] || 'bg-gray-100 text-gray-600', className)}>
      {label}
    </span>
  )
}
