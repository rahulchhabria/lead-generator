import clsx from 'clsx'

export function Card({ children, className, onClick }: { children: React.ReactNode; className?: string; onClick?: () => void }) {
  return <div className={clsx('bg-white rounded-xl border border-gray-200 shadow-sm', onClick && 'cursor-pointer', className)} onClick={onClick}>{children}</div>
}
export function CardHeader({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={clsx('px-6 py-4 border-b border-gray-100', className)}>{children}</div>
}
export function CardBody({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={clsx('px-6 py-4', className)}>{children}</div>
}
