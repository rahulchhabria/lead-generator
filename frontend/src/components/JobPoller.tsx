import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

export function JobPoller({ jobId, onComplete, onError }: { jobId: string; onComplete?: (r: unknown) => void; onError?: (e: string) => void }) {
  const { data } = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => api.jobs.get(jobId),
    refetchInterval: (q) => { const s = q.state.data?.status; return (s === 'running' || s === 'pending') ? 1500 : false },
  })
  useEffect(() => {
    if (!data) return
    if (data.status === 'completed' && onComplete) onComplete(data.result)
    if (data.status === 'failed' && onError) onError(data.error || 'Unknown error')
  }, [data?.status])
  if (!data) return null
  return (
    <div className="space-y-2">
      <div className="flex justify-between text-sm">
        <span className="text-gray-600">{data.message || data.status}</span>
        <span className="text-gray-500">{data.progress}%</span>
      </div>
      <div className="w-full bg-gray-100 rounded-full h-2">
        <div className={`h-2 rounded-full transition-all duration-500 ${data.status === 'failed' ? 'bg-red-500' : 'bg-brand-500'}`} style={{ width: `${data.progress}%` }} />
      </div>
      {data.status === 'failed' && <p className="text-sm text-red-600">{data.error}</p>}
    </div>
  )
}
