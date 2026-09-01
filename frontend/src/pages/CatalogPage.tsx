import { useEffect, useRef } from 'react'
import { Search, Loader2, AlertCircle, Plus, UserCheck } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useLandings } from '../hooks/useLandings'
import { useAuth } from '../hooks/useAuth'
import LandingCard from '../components/LandingCard'

export default function CatalogPage() {
  const { data, loading, error, page, setPage, search, setSearch, mine, setMine, refetch } = useLandings()
  const { user } = useAuth()
  const thumbAttempts = useRef(0)

  // Thumbnails are generated in background on the server; refetch a few times
  // so cards pick them up as soon as they are ready.
  useEffect(() => {
    if (!data) return
    const missing = data.items.some((i) => i.status === 'ready' && !i.thumbnail_url)
    if (!missing || thumbAttempts.current >= 4) return
    thumbAttempts.current += 1
    const t = setTimeout(() => refetch(), 9000)
    return () => clearTimeout(t)
  }, [data])

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-8">
        <div>
          <h1 className="text-2xl font-bold text-text">Витрина лендингов</h1>
          <p className="text-text-muted mt-1">
            {data ? `${data.total} лендингов` : 'Загрузка...'}
          </p>
        </div>
        <Link
          to="/generate"
          className="inline-flex items-center gap-2 px-4 py-2.5 bg-primary hover:bg-primary-hover text-white rounded-lg font-medium text-sm transition-colors no-underline"
        >
          <Plus size={18} />
          Создать лендинг
        </Link>
      </div>

      <div className="flex gap-2 mb-6">
        <div className="relative flex-1">
          <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
          <input
            type="text"
            placeholder="Поиск лендингов..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 bg-surface border border-border rounded-lg text-text placeholder:text-text-muted focus:outline-none focus:border-primary transition-colors"
          />
        </div>
        {user && (
          <button
            onClick={() => { setPage(1); setMine(!mine) }}
            className={`inline-flex items-center gap-1.5 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors border shrink-0 ${
              mine
                ? 'bg-primary/15 text-primary border-primary/30'
                : 'bg-surface border-border text-text-muted hover:bg-surface-hover'
            }`}
            title="Показать мои работы, включая черновики"
          >
            <UserCheck size={15} />
            Только мои
          </button>
        )}
      </div>

      {error && (
        <div className="bg-danger/10 border border-danger/30 rounded-lg p-4 mb-6 flex items-center gap-3">
          <AlertCircle size={18} className="text-danger shrink-0" />
          <div className="flex-1">
            <p className="text-danger text-sm">{error}</p>
          </div>
          <button
            onClick={refetch}
            className="text-sm text-danger hover:underline cursor-pointer"
          >
            Повторить
          </button>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 size={32} className="animate-spin text-primary" />
        </div>
      ) : data && data.items.length === 0 ? (
        <div className="text-center py-20">
          <div className="text-6xl mb-4 text-text-muted/20">L</div>
          <p className="text-text-muted text-lg mb-4">Лендингов пока нет</p>
          <Link
            to="/generate"
            className="inline-flex items-center gap-2 px-4 py-2.5 bg-primary hover:bg-primary-hover text-white rounded-lg font-medium text-sm transition-colors no-underline"
          >
            <Plus size={18} />
            Создать первый лендинг
          </Link>
        </div>
      ) : data ? (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {data.items.map((landing) => (
              <LandingCard key={landing.id} landing={landing} />
            ))}
          </div>

          {data.pages > 1 && (
            <div className="flex items-center justify-center gap-2 mt-8">
              <button
                onClick={() => setPage(page - 1)}
                disabled={page <= 1}
                className="px-3 py-1.5 rounded-lg text-sm bg-surface border border-border text-text disabled:opacity-40 disabled:cursor-not-allowed hover:bg-surface-hover transition-colors"
              >
                Назад
              </button>
              <span className="text-text-muted text-sm px-3">
                {page} / {data.pages}
              </span>
              <button
                onClick={() => setPage(page + 1)}
                disabled={page >= data.pages}
                className="px-3 py-1.5 rounded-lg text-sm bg-surface border border-border text-text disabled:opacity-40 disabled:cursor-not-allowed hover:bg-surface-hover transition-colors"
              >
                Вперёд
              </button>
            </div>
          )}
        </>
      ) : null}
    </div>
  )
}
