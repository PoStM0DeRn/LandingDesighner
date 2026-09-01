import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Send, Upload, X, Loader2, AlertCircle, Settings, Lock, LogIn, Image as ImageIcon } from 'lucide-react'
import { generateLanding } from '../api/client'
import { useSettings } from '../hooks/useSettings'
import { useAuth } from '../hooks/useAuth'
import SkillsSelector from '../components/SkillsSelector'

export default function GeneratePage() {
  const navigate = useNavigate()
  const { settings } = useSettings()
  const { user, openAuthModal } = useAuth()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [prompt, setPrompt] = useState('')
  const [title, setTitle] = useState('')
  const [tags, setTags] = useState('')
  const [brandbook, setBrandbook] = useState<File | null>(null)
  const [workflow, setWorkflow] = useState<File | null>(null)
  const wfInputRef = useRef<HTMLInputElement>(null)
  const [selectedSkills, setSelectedSkills] = useState<string[]>([])
  const [useLlmMarkup, setUseLlmMarkup] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) setBrandbook(file)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!prompt.trim()) return

    setLoading(true)
    setError(null)

    try {
      const result = await generateLanding({
        prompt: prompt.trim(),
        title: title.trim() || undefined,
        tags: tags.split(',').map((t) => t.trim()).filter(Boolean),
        brandbook: brandbook || undefined,
        provider: settings.provider,
        model: settings.provider === 'local' ? settings.localModel : settings.openaiModel,
        apiEndpoint: settings.provider === 'local' ? settings.localUrl : undefined,
        apiKey: settings.provider === 'openai' ? settings.openaiKey : undefined,
        skillIds: selectedSkills,
        comfyuiWorkflowPath: settings.comfyuiWorkflowPath || undefined,
        comfyuiUrl: settings.comfyuiUrl || undefined,
        workflow: workflow || undefined,
        imageSteps: settings.imageSteps,
        useLlmMarkup,
      })
      navigate(`/landing/${result.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка при генерации')
    } finally {
      setLoading(false)
    }
  }

  const providerLabel = settings.provider === 'local' ? 'LM Studio' : 'OpenAI'
  const modelLabel = settings.provider === 'local' ? settings.localModel : settings.openaiModel

  if (!user) {
    return (
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-20 text-center">
        <Lock size={48} className="mx-auto text-text-muted/40 mb-4" />
        <h1 className="text-xl font-bold text-text mb-2">Войдите, чтобы генерировать</h1>
        <p className="text-text-muted mb-6">
          Работы подписываются вашим никнеймом и появляются на витрине с указанием автора.
        </p>
        <button
          onClick={openAuthModal}
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-primary hover:bg-primary-hover text-white rounded-lg font-medium text-sm transition-colors"
        >
          <LogIn size={16} />
          Войти или зарегистрироваться
        </button>
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <h1 className="text-2xl font-bold text-text mb-2">Генерация лендинга</h1>
      <p className="text-text-muted mb-6">
        Опишите желаемый лендинг, и AI создаст его для вас
      </p>

      {/* Current model info */}
      <div className="flex items-center gap-2 px-4 py-2.5 bg-surface border border-border rounded-lg mb-6">
        <Settings size={14} className="text-text-muted" />
        <span className="text-xs text-text-muted">
          Провайдер: <span className="text-text font-medium">{providerLabel}</span>
          {' '}&middot;{' '}
          Модель: <span className="text-text font-medium">{modelLabel}</span>
          {selectedSkills.length > 0 && (
            <>
              {' '}&middot;{' '}
              Скиллы: <span className="text-text font-medium">{selectedSkills.length}</span>
            </>
          )}
        </span>
      </div>

      {error && (
        <div className="bg-danger/10 border border-danger/30 rounded-lg p-4 mb-6 flex items-center gap-3">
          <AlertCircle size={18} className="text-danger shrink-0" />
          <p className="text-danger text-sm">{error}</p>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label className="block text-sm font-medium text-text mb-2">
            Описание лендинга <span className="text-danger">*</span>
          </label>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Например: Лендинг для IT-студии, которая разрабатывает мобильные приложения. минималистичный стиль, тёмная тема, акцент на cyan..."
            rows={5}
            className="w-full px-4 py-3 bg-surface border border-border rounded-lg text-text placeholder:text-text-muted focus:outline-none focus:border-primary transition-colors resize-none"
            required
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-text mb-2">
            Название (опционально)
          </label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Название вашего лендинга"
            className="w-full px-4 py-2.5 bg-surface border border-border rounded-lg text-text placeholder:text-text-muted focus:outline-none focus:border-primary transition-colors"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-text mb-2">
            Теги (через запятую, опционально)
          </label>
          <input
            type="text"
            value={tags}
            onChange={(e) => setTags(e.target.value)}
            placeholder="IT, мобильные приложения, стартап"
            className="w-full px-4 py-2.5 bg-surface border border-border rounded-lg text-text placeholder:text-text-muted focus:outline-none focus:border-primary transition-colors"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-text mb-2">
            Скиллы (опционально)
          </label>
          <p className="text-xs text-text-muted mb-2">
            Выберите инструкции для улучшения генерации
          </p>
          <SkillsSelector selected={selectedSkills} onChange={setSelectedSkills} />
        </div>

        <div>
          <label className="block text-sm font-medium text-text mb-2">
            Workflow ComfyUI (опционально)
          </label>
          <div
            onClick={() => wfInputRef.current?.click()}
            className="border-2 border-dashed border-border rounded-lg p-4 text-center cursor-pointer hover:border-primary/50 transition-colors"
          >
            {workflow ? (
              <div className="flex items-center justify-center gap-3">
                <ImageIcon size={20} className="text-primary" />
                <span className="text-text text-sm">{workflow.name}</span>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation()
                    setWorkflow(null)
                  }}
                  className="p-1 rounded hover:bg-surface-hover transition-colors"
                >
                  <X size={14} className="text-text-muted" />
                </button>
              </div>
            ) : (
              <p className="text-text-muted text-sm">
                Приложи свой txt2img workflow (JSON, UI- или API-формат ComfyUI)
              </p>
            )}
          </div>
          <input
            ref={wfInputRef}
            type="file"
            accept=".json"
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) setWorkflow(f)
            }}
            className="hidden"
          />
          <p className="text-xs text-text-muted mt-1">
            Изображения будут рендериться на ComfyUI по URL из настроек.
          </p>
        </div>

        <div>
          <label className="block text-sm font-medium text-text mb-2">
            Разметка секций
          </label>
          <label className="flex items-start gap-3 bg-surface border border-border rounded-lg p-4 cursor-pointer hover:border-primary/50 transition-colors">
            <input
              type="checkbox"
              checked={useLlmMarkup}
              onChange={(e) => setUseLlmMarkup(e.target.checked)}
              className="mt-0.5 h-4 w-4 accent-primary"
            />
            <span>
              <span className="text-sm text-text font-medium block">AI-дизайнер разметки (эксперимент)</span>
              <span className="text-xs text-text-muted">
                LLM создаёт уникальный HTML каждой секции вместо готовых шаблонов. Дольше, но разнообразнее.
              </span>
            </span>
          </label>
        </div>

        <div>
          <label className="block text-sm font-medium text-text mb-2">
            Брендбук (опционально)
          </label>
          <div
            onClick={() => fileInputRef.current?.click()}
            className="border-2 border-dashed border-border rounded-lg p-6 text-center cursor-pointer hover:border-primary/50 transition-colors"
          >
            {brandbook ? (
              <div className="flex items-center justify-center gap-3">
                <Upload size={20} className="text-primary" />
                <span className="text-text text-sm">{brandbook.name}</span>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation()
                    setBrandbook(null)
                  }}
                  className="p-1 rounded hover:bg-surface-hover transition-colors"
                >
                  <X size={14} className="text-text-muted" />
                </button>
              </div>
            ) : (
              <div>
                <Upload size={24} className="mx-auto text-text-muted mb-2" />
                <p className="text-text-muted text-sm">
                  Перетащите файл или нажмите для выбора
                </p>
                <p className="text-text-muted/60 text-xs mt-1">
                  PDF, JSON или YAML
                </p>
              </div>
            )}
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.json,.yaml,.yml"
            onChange={handleFileChange}
            className="hidden"
          />
        </div>

        <button
          type="submit"
          disabled={loading || !prompt.trim()}
          className="w-full inline-flex items-center justify-center gap-2 px-6 py-3 bg-primary hover:bg-primary-hover text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? (
            <>
              <Loader2 size={18} className="animate-spin" />
              Генерация...
            </>
          ) : (
            <>
              <Send size={18} />
              Сгенерировать
            </>
          )}
        </button>
      </form>
    </div>
  )
}
