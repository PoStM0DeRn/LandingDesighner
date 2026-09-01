import { useEffect, useRef, useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, Download, Eye, Trash2, Loader2, AlertCircle, CheckCircle2,
  RefreshCw, Image as ImageIcon, Type, ChevronDown, Cpu, User, Globe, EyeOff, Copy, Check,
} from 'lucide-react'
import {
  getLanding, getLandingHtml, getLandingCss, deleteLanding,
  getLandingSections, regenerateLandingImage, regenerateLandingSection,
  getGenerationInfo, publishLanding,
} from '../api/client'
import { useAuth } from '../hooks/useAuth'
import type { LandingDetail, GenerationInfo, SectionSummary } from '../types'
import PreviewModal from '../components/PreviewModal'

const STAGE_FRACTION: Record<string, number> = {
  queued: 0.05,
  parse_intent: 0.12,
  generate_content: 0.3,
  generate_design: 0.42,
  generate_images: 0.62,
  generate_markup: 0.8,
  assemble: 0.9,
  finalize: 0.97,
}

const IMAGE_SECTION_TYPES = new Set(['hero', 'features', 'about', 'services', 'testimonials'])

interface Progress {
  stage: string
  message: string
  images_done: number
  images_total: number
  notice?: string
}

function progressWidth(p: Progress | null): string {
  if (!p) return '5%'
  if (p.stage === 'generate_images' && p.images_total > 0) {
    const frac = 0.5 + 0.4 * (p.images_done / p.images_total)
    return `${Math.round(frac * 100)}%`
  }
  return `${Math.round((STAGE_FRACTION[p.stage] ?? 0.5) * 100)}%`
}

export default function LandingDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { user } = useAuth()
  const [landing, setLanding] = useState<LandingDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showPreview, setShowPreview] = useState(false)
  const [html, setHtml] = useState('')
  const [htmlLoading, setHtmlLoading] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [publishing, setPublishing] = useState(false)
  const [progress, setProgress] = useState<Progress | null>(null)
  const [sections, setSections] = useState<SectionSummary[]>([])
  const [regenBusy, setRegenBusy] = useState<string | null>(null)
  const [genInfo, setGenInfo] = useState<GenerationInfo | null>(null)
  const [expandedSkill, setExpandedSkill] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const esRef = useRef<EventSource | null>(null)

  const fetchSections = (landingId: string) => {
    getLandingSections(landingId)
      .then(setSections)
      .catch(() => setSections([]))
  }

  const fetchGenInfo = (landingId: string) => {
    getGenerationInfo(landingId)
      .then(setGenInfo)
      .catch(() => setGenInfo(null))
  }

  const refetchMeta = (landingId: string) => {
    getLanding(landingId).then(setLanding).catch(() => {})
  }

  useEffect(() => {
    if (!id) return
    let active = true
    setLoading(true)

    const stopPolling = () => {
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
    }
    const stopEvents = () => {
      if (esRef.current) {
        esRef.current.close()
        esRef.current = null
      }
    }

    const onFinal = () => {
      stopPolling()
      stopEvents()
      if (!active || !id) return
      refetchMeta(id)
      fetchSections(id)
      fetchGenInfo(id)
    }

    const poll = () => {
      getLanding(id)
        .then((data) => {
          if (!active) return
          setLanding(data)
          setLoading(false)
          if (data.status === 'generating') {
            if (!pollRef.current) {
              pollRef.current = setInterval(poll, 2000)
            }
          } else {
            onFinal()
          }
        })
        .catch((err) => {
          if (active) setError(err instanceof Error ? err.message : 'Failed to load')
        })
    }

    poll()

    // SSE for live progress; polling remains as fallback
    const es = new EventSource(`/api/landings/${id}/events`)
    esRef.current = es
    es.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data)
        if (data.status === 'not_found') {
          es.close()
          return
        }
        setProgress(data.progress ?? null)
        if (data.status && data.status !== 'generating') {
          es.close()
          onFinal()
        }
      } catch {
        /* ignore malformed events */
      }
    }
    es.onerror = () => {
      // SSE dropped — polling fallback keeps working
      es.close()
      if (esRef.current === es) esRef.current = null
    }

    return () => {
      active = false
      stopPolling()
      stopEvents()
    }
  }, [id])

  const handlePreview = async () => {
    if (!id) return
    setHtmlLoading(true)
    try {
      const content = await getLandingHtml(id)
      let finalHtml = content
      const css = await getLandingCss(id)
      if (css) {
        // Compiled Tailwind build: inline the stylesheet for the srcdoc iframe
        finalHtml = content
          .replace('<link rel="stylesheet" href="styles.css">', `<style>${css}</style>`)
          .replace(/<script src="https:\/\/cdn\.tailwindcss\.com"><\/script>/, '')
      }
      setHtml(finalHtml)
      setShowPreview(true)
    } catch {
      setError('Не удалось загрузить HTML')
    } finally {
      setHtmlLoading(false)
    }
  }

  const handleDelete = async () => {
    if (!id || !confirm('Удалить этот лендинг?')) return
    setDeleting(true)
    try {
      await deleteLanding(id)
      navigate('/')
    } catch {
      setError('Не удалось удалить лендинг')
      setDeleting(false)
    }
  }

  const handlePublish = async (published: boolean) => {
    if (!id) return
    setPublishing(true)
    setError(null)
    try {
      await publishLanding(id, published)
      refetchMeta(id)
    } catch (e) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail || 'Не удалось изменить публикацию')
    } finally {
      setPublishing(false)
    }
  }

  const handleCopyPrompt = async () => {
    if (!landing) return
    try {
      await navigator.clipboard.writeText(landing.prompt)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      /* clipboard unavailable */
    }
  }

  const handleRegenImage = async (sectionType: string, itemIndex?: number) => {
    if (!id) return
    const key = `${sectionType}:img:${itemIndex ?? 'main'}`
    setRegenBusy(key)
    setError(null)
    try {
      await regenerateLandingImage(id, sectionType, itemIndex)
      refetchMeta(id)
      fetchSections(id)
      // thumbnail refreshes in background — pick it up shortly after
      setTimeout(() => refetchMeta(id), 8000)
    } catch (e) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail || 'Не удалось перегенерировать изображение')
    } finally {
      setRegenBusy(null)
    }
  }

  const handleRegenSection = async (sectionType: string) => {
    if (!id) return
    const key = `${sectionType}:text`
    setRegenBusy(key)
    setError(null)
    try {
      await regenerateLandingSection(id, sectionType)
      fetchSections(id)
    } catch (e) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail || 'Не удалось перегенерировать секцию')
    } finally {
      setRegenBusy(null)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 size={32} className="animate-spin text-primary" />
      </div>
    )
  }

  if (error && !landing) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-20 text-center">
        <AlertCircle size={48} className="mx-auto text-danger mb-4" />
        <p className="text-text-muted mb-4">{error || 'Лендинг не найден'}</p>
        <Link to="/" className="text-primary hover:underline">
          Вернуться к витрине
        </Link>
      </div>
    )
  }

  if (!landing) return null

  const isGenerating = landing.status === 'generating'
  const canManage = !!user && (!landing.owner_nickname || landing.owner_nickname === user.nickname)
  const isDraft = landing.published === false

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <button
        onClick={() => navigate(-1)}
        className="inline-flex items-center gap-2 text-text-muted hover:text-text text-sm mb-6 transition-colors"
      >
        <ArrowLeft size={16} />
        Назад
      </button>

      {error && landing && (
        <div className="bg-danger/10 border border-danger/30 rounded-lg p-4 mb-4 flex items-center gap-3">
          <AlertCircle size={18} className="text-danger shrink-0" />
          <p className="text-danger text-sm">{error}</p>
        </div>
      )}

      {isDraft && (
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-4 mb-4 flex items-start gap-3">
          <EyeOff size={18} className="text-amber-600 shrink-0 mt-0.5" />
          <p className="text-amber-700 text-sm">
            Черновик — работа не видна на витрине. Нажмите «Опубликовать», чтобы поделиться.
          </p>
        </div>
      )}

      <div className="bg-surface rounded-xl border border-border overflow-hidden">
        <div className="aspect-video bg-bg relative">
          {isGenerating && (
            <div className="absolute inset-0 bg-black/60 flex flex-col items-center justify-center z-10">
              <Loader2 size={40} className="animate-spin text-white mb-3" />
              <p className="text-white font-medium">
                {progress?.message || 'Генерация лендинга...'}
              </p>
              {progress?.images_total ? (
                <p className="text-white/70 text-sm mt-1">
                  Изображений: {progress.images_done}/{progress.images_total}
                </p>
              ) : null}
              {progress?.notice && (
                <p className="text-amber-300 text-xs mt-2 max-w-md text-center">{progress.notice}</p>
              )}
              <div className="w-56 h-1.5 bg-white/20 rounded-full mt-4 overflow-hidden">
                <div
                  className="h-full bg-white/80 rounded-full transition-all duration-700"
                  style={{ width: progressWidth(progress) }}
                />
              </div>
            </div>
          )}
          {landing.thumbnail_url ? (
            <img src={landing.thumbnail_url} alt={landing.title} className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full flex items-center justify-center">
              <div className="text-6xl text-text-muted/20 font-bold">L</div>
            </div>
          )}
        </div>

        <div className="p-6">
          <div className="flex items-start justify-between gap-4 mb-4">
            <div>
              <h1 className="text-xl font-bold text-text mb-1">{landing.title}</h1>
              <p className="text-text-muted text-sm">
                {new Date(landing.created_at).toLocaleString('ru-RU')}
              </p>
              <p className="text-text-muted text-sm flex items-center gap-1 mt-0.5">
                <User size={12} />
                Автор: {landing.owner_nickname || 'Гость'}
              </p>
              {isGenerating && (
                <p className="text-primary text-sm mt-1 flex items-center gap-1">
                  <Loader2 size={14} className="animate-spin" />
                  {progress?.message || 'Генерация...'}
                </p>
              )}
              {landing.status === 'ready' && (
                <p className="text-green-600 text-sm mt-1 flex items-center gap-1">
                  <CheckCircle2 size={14} />
                  Готово
                </p>
              )}
              {landing.status === 'error' && (
                <p className="text-danger text-sm mt-1 flex items-center gap-1">
                  <AlertCircle size={14} />
                  Ошибка генерации
                </p>
              )}
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {canManage && (isDraft ? (
                <button
                  onClick={() => handlePublish(true)}
                  disabled={publishing || isGenerating}
                  title="Опубликовать на витрине"
                  className="inline-flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                >
                  {publishing ? <Loader2 size={16} className="animate-spin" /> : <Globe size={16} />}
                  <span className="hidden sm:inline">Опубликовать</span>
                </button>
              ) : (
                <button
                  onClick={() => handlePublish(false)}
                  disabled={publishing}
                  title="Снять с публикации"
                  className="inline-flex items-center gap-2 px-4 py-2 bg-amber-500/10 hover:bg-amber-500/20 text-amber-600 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                >
                  {publishing ? <Loader2 size={16} className="animate-spin" /> : <EyeOff size={16} />}
                  <span className="hidden sm:inline">Снять</span>
                </button>
              ))}
              <button
                onClick={handlePreview}
                disabled={htmlLoading || isGenerating}
                className="inline-flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary-hover text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
              >
                {htmlLoading ? <Loader2 size={16} className="animate-spin" /> : <Eye size={16} />}
                Предпросмотр
              </button>
              <a
                href={`/api/landings/${landing.id}/download`}
                className="inline-flex items-center gap-2 px-4 py-2 bg-accent/10 hover:bg-accent/20 text-accent rounded-lg text-sm font-medium transition-colors no-underline"
              >
                <Download size={16} />
                Скачать
              </a>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="inline-flex items-center gap-2 px-3 py-2 bg-danger/10 hover:bg-danger/20 text-danger rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
              >
                {deleting ? <Loader2 size={16} className="animate-spin" /> : <Trash2 size={16} />}
              </button>
            </div>
          </div>

          {landing.status === 'error' && landing.error_message && (
            <div className="bg-danger/10 border border-danger/30 rounded-lg p-4 mb-4 flex items-start gap-3">
              <AlertCircle size={18} className="text-danger shrink-0 mt-0.5" />
              <div>
                <p className="text-danger text-sm font-medium mb-0.5">Ошибка генерации</p>
                <p className="text-danger/80 text-sm">{landing.error_message}</p>
              </div>
            </div>
          )}

          {landing.description && (
            <p className="text-text-muted text-sm mb-4">{landing.description}</p>
          )}

          {sections.length > 0 && (
            <div className="mb-4">
              <h3 className="text-xs uppercase text-text-muted font-medium mb-2">Секции</h3>
              <div className="space-y-1.5">
                {sections.map((s) => (
                  <div key={`${s.index}-${s.type}`} className="bg-bg rounded-lg px-3 py-2">
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <span className="text-xs text-text-muted/60 uppercase mr-2">{s.type}</span>
                        <span className="text-sm text-text truncate">{s.title || '—'}</span>
                      </div>
                      <div className="flex items-center gap-1 shrink-0">
                        {IMAGE_SECTION_TYPES.has(s.type) && (
                          <button
                            onClick={() => handleRegenImage(s.type)}
                            disabled={regenBusy !== null}
                            title="Перегенерировать изображение"
                            className="p-1.5 rounded-lg text-text-muted hover:text-primary hover:bg-primary/10 transition-colors disabled:opacity-40"
                          >
                            {regenBusy === `${s.type}:img:main`
                              ? <Loader2 size={14} className="animate-spin" />
                              : <ImageIcon size={14} />}
                          </button>
                        )}
                        <button
                          onClick={() => handleRegenSection(s.type)}
                          disabled={regenBusy !== null}
                          title="Перегенерировать текст секции"
                          className="p-1.5 rounded-lg text-text-muted hover:text-accent hover:bg-accent/10 transition-colors disabled:opacity-40"
                        >
                          {regenBusy === `${s.type}:text`
                            ? <Loader2 size={14} className="animate-spin" />
                            : <Type size={14} />}
                        </button>
                      </div>
                    </div>
                    {IMAGE_SECTION_TYPES.has(s.type) && (s.item_titles?.length ?? 0) > 0 && (
                      <div className="mt-1.5 ml-4 space-y-1">
                        {s.item_titles!.map((t, i) => (
                          <div
                            key={`${s.index}-item-${i}`}
                            className="flex items-center justify-between gap-2 bg-surface-hover/40 rounded px-2 py-1"
                          >
                            <span className="text-xs text-text-muted truncate">{t}</span>
                            <button
                              onClick={() => handleRegenImage(s.type, i)}
                              disabled={regenBusy !== null}
                              title="Перегенерировать изображение карточки"
                              className="p-1 rounded text-text-muted hover:text-primary hover:bg-primary/10 transition-colors disabled:opacity-40 shrink-0"
                            >
                              {regenBusy === `${s.type}:img:${i}`
                                ? <Loader2 size={12} className="animate-spin" />
                                : <ImageIcon size={12} />}
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
              <button
                onClick={() => id && fetchSections(id)}
                className="mt-2 inline-flex items-center gap-1 text-xs text-text-muted hover:text-text transition-colors"
              >
                <RefreshCw size={11} />
                Обновить список
              </button>
            </div>
          )}

          {genInfo && (
            <div className="mb-4">
              <h3 className="text-xs uppercase text-text-muted font-medium mb-2 flex items-center gap-1.5">
                <Cpu size={12} />
                Как сгенерирован
              </h3>
              <div className="bg-bg rounded-lg p-4 space-y-3">
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
                  <span className="text-text-muted">
                    Провайдер:{' '}
                    <span className="text-text">
                      {genInfo.provider === 'openai' ? 'OpenAI' : genInfo.provider === 'local' ? 'LM Studio' : '—'}
                    </span>
                  </span>
                  <span className="text-text-muted">
                    Модель: <span className="text-text font-medium">{genInfo.model || '—'}</span>
                  </span>
                  {genInfo.available && (
                    <span className="text-text-muted">
                      Разметка: <span className="text-text">{genInfo.use_llm_markup ? 'AI-дизайнер' : 'Шаблоны'}</span>
                    </span>
                  )}
                  {genInfo.image_steps != null && (
                    <span className="text-text-muted">
                      Изображения: <span className="text-text">{genInfo.image_steps} шаг.</span>
                    </span>
                  )}
                </div>

                {genInfo.tokens && (() => {
                  const t = genInfo.tokens
                  const palette = Array.from(new Set(
                    [t.primary_color, t.secondary_color, t.accent_color, t.bg_color, t.text_color].filter(Boolean) as string[],
                  ))
                  if (palette.length === 0 && !t.heading_font && !t.body_font) return null
                  return (
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
                      {palette.length > 0 && (
                        <div className="flex items-center gap-1.5">
                          <span className="text-text-muted">Палитра:</span>
                          {palette.map((c) => (
                            <span
                              key={c}
                              title={c}
                              className="inline-block w-4 h-4 rounded border border-border"
                              style={{ backgroundColor: c }}
                            />
                          ))}
                        </div>
                      )}
                      {(t.heading_font || t.body_font) && (
                        <span className="text-text-muted">
                          Шрифты: <span className="text-text">{[t.heading_font, t.body_font].filter(Boolean).join(' / ')}</span>
                        </span>
                      )}
                    </div>
                  )
                })()}

                {genInfo.intent?.topic && (
                  <div className="text-sm text-text-muted">
                    Намерение: <span className="text-text">«{genInfo.intent.topic}»</span>
                    {genInfo.intent.style && <> · стиль <span className="text-text">{genInfo.intent.style}</span></>}
                    {genInfo.intent.tone && <> · тон <span className="text-text">{genInfo.intent.tone}</span></>}
                  </div>
                )}

                {genInfo.skills.length > 0 && (
                  <div>
                    <div className="text-sm text-text-muted mb-1.5">Скиллы ({genInfo.skills.length}):</div>
                    <div className="space-y-1.5">
                      {genInfo.skills.map((s) => (
                        <div key={s.name} className="border border-border rounded-lg overflow-hidden">
                          <button
                            onClick={() => setExpandedSkill(expandedSkill === s.name ? null : s.name)}
                            className="w-full flex items-center justify-between px-3 py-2 hover:bg-surface-hover transition-colors text-left"
                          >
                            <span className="text-sm text-text">{s.name}</span>
                            <ChevronDown
                              size={14}
                              className={`text-text-muted shrink-0 transition-transform ${expandedSkill === s.name ? 'rotate-180' : ''}`}
                            />
                          </button>
                          {expandedSkill === s.name && (
                            <div className="px-3 pb-3">
                              {s.description && <p className="text-xs text-text-muted mb-1.5">{s.description}</p>}
                              <pre className="bg-surface rounded-lg p-2.5 text-xs text-text-muted font-mono whitespace-pre-wrap overflow-x-auto">
                                {s.prompt_addition}
                              </pre>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {!genInfo.available && (
                  <p className="text-xs text-text-muted/70">
                    Детали генерации недоступны — лендинг создан старой версией приложения.
                  </p>
                )}
              </div>
            </div>
          )}

          <div className="mb-4">
            <h3 className="text-xs uppercase text-text-muted font-medium mb-2 flex items-center gap-2">
              Промпт
              <button
                onClick={handleCopyPrompt}
                className="inline-flex items-center gap-1 text-xs normal-case text-text-muted hover:text-primary transition-colors"
                title="Скопировать промпт"
              >
                {copied ? <Check size={12} className="text-green-600" /> : <Copy size={12} />}
                {copied ? 'Скопировано' : 'Копировать'}
              </button>
            </h3>
            <div className="bg-bg rounded-lg p-3 text-sm text-text-muted font-mono whitespace-pre-wrap">
              {landing.prompt}
            </div>
          </div>

          {landing.tags.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {landing.tags.map((tag) => (
                <span key={tag} className="text-xs bg-surface-hover text-text-muted px-2.5 py-1 rounded-full">
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {showPreview && (
        <PreviewModal
          html={html}
          title={landing.title}
          landingId={landing.id}
          onClose={() => setShowPreview(false)}
        />
      )}
    </div>
  )
}
