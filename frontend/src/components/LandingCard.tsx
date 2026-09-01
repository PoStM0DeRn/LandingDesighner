import { Eye, Download, Tag, User } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { Landing } from '../types'

interface LandingCardProps {
  landing: Landing
}

const statusColors = {
  ready: 'bg-success/15 text-success',
  generating: 'bg-amber-500/15 text-amber-600',
  error: 'bg-danger/15 text-danger',
}

const statusLabels = {
  ready: 'Готово',
  generating: 'Генерация...',
  error: 'Ошибка',
}

export default function LandingCard({ landing }: LandingCardProps) {
  return (
    <div className="group bg-surface rounded-xl border border-border overflow-hidden hover:border-primary/50 transition-all duration-200">
      <div className="aspect-video bg-bg relative overflow-hidden">
        {landing.thumbnail_url ? (
          <img
            src={landing.thumbnail_url}
            alt={landing.title}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <div className="text-4xl text-text-muted/30 font-bold">L</div>
          </div>
        )}
        <div className="absolute top-2 right-2 flex items-center gap-1">
          {landing.published === false && (
            <span className="text-xs font-medium px-2 py-1 rounded-full bg-amber-500/90 text-white">
              Черновик
            </span>
          )}
          <span className={`text-xs font-medium px-2 py-1 rounded-full ${statusColors[landing.status]}`}>
            {statusLabels[landing.status]}
          </span>
        </div>
        <div className="absolute top-2 left-2 flex flex-col items-start gap-1">
          {landing.model && (
            <span
              className="text-xs font-medium px-2 py-1 rounded-full bg-black/50 text-white backdrop-blur-sm"
              title={`Сгенерировано моделью ${landing.model}`}
            >
              {landing.model.split('/').pop()}
            </span>
          )}
          <span
            className="text-xs px-2 py-1 rounded-full bg-black/40 text-white/90 backdrop-blur-sm inline-flex items-center gap-1"
            title={`Автор: ${landing.owner_nickname || 'Гость'}`}
          >
            <User size={10} />
            {landing.owner_nickname || 'Гость'}
          </span>
        </div>
      </div>

      <div className="p-4">
        <h3 className="text-text font-semibold text-base mb-1 truncate">
          {landing.title}
        </h3>
        <p className="text-text-muted text-sm mb-3 line-clamp-2">
          {landing.description || landing.prompt}
        </p>

        {landing.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-3">
            {landing.tags.slice(0, 3).map((tag) => (
              <span key={tag} className="inline-flex items-center gap-1 text-xs bg-surface-hover text-text-muted px-2 py-0.5 rounded-full">
                <Tag size={10} />
                {tag}
              </span>
            ))}
            {landing.tags.length > 3 && (
              <span className="text-xs text-text-muted">+{landing.tags.length - 3}</span>
            )}
          </div>
        )}

        <div className="flex items-center justify-between pt-2 border-t border-border">
          <span className="text-xs text-text-muted">
            {new Date(landing.created_at).toLocaleDateString('ru-RU')}
          </span>
          <div className="flex items-center gap-1">
            <Link
              to={`/landing/${landing.id}`}
              className="p-2 rounded-lg text-text-muted hover:text-primary hover:bg-primary/10 transition-colors no-underline"
              title="Просмотр"
            >
              <Eye size={16} />
            </Link>
            <a
              href={`/api/landings/${landing.id}/download`}
              className="p-2 rounded-lg text-text-muted hover:text-accent hover:bg-accent/10 transition-colors no-underline"
              title="Скачать"
            >
              <Download size={16} />
            </a>
          </div>
        </div>
      </div>
    </div>
  )
}
