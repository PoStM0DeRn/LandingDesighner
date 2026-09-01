import { Link } from 'react-router-dom'
import { Compass } from 'lucide-react'

export default function NotFoundPage() {
  return (
    <div className="max-w-3xl mx-auto px-4 py-20 text-center">
      <Compass size={48} className="mx-auto text-text-muted/40 mb-4" />
      <h1 className="text-2xl font-bold text-text mb-2">404</h1>
      <p className="text-text-muted mb-6">Такой страницы не существует.</p>
      <Link
        to="/"
        className="inline-flex items-center gap-2 px-5 py-2.5 bg-primary hover:bg-primary-hover text-white rounded-lg font-medium text-sm transition-colors no-underline"
      >
        На витрину
      </Link>
    </div>
  )
}
