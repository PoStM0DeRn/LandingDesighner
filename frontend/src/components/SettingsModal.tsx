import { useEffect, useState } from 'react'
import { X, Settings, Monitor, Cloud, Server, RefreshCw, Loader2, AlertCircle, Image } from 'lucide-react'
import api from '../api/client'
import { useSettings, OPENAI_MODELS, type LLMProvider } from '../hooks/useSettings'

interface SettingsModalProps {
  onClose: () => void
}

export default function SettingsModal({ onClose }: SettingsModalProps) {
  const { settings, update, localModels, modelsLoading, modelsError, refreshModels } = useSettings()
  const [tab, setTab] = useState<LLMProvider | 'comfyui'>(settings.provider)
  const [comfyStatus, setComfyStatus] = useState<{ comfyui: boolean; npm: boolean } | null>(null)

  useEffect(() => {
    if (tab !== 'comfyui') return
    let active = true
    api.get('/health', { timeout: 10000 })
      .then(({ data }) => { if (active) setComfyStatus({ comfyui: !!data.comfyui, npm: !!data.npm }) })
      .catch(() => { if (active) setComfyStatus({ comfyui: false, npm: false }) })
    return () => { active = false }
  }, [tab])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-800/40 backdrop-blur-sm p-4">
      <div className="bg-surface rounded-2xl border border-border w-full max-w-lg overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <div className="flex items-center gap-2">
            <Settings size={18} className="text-text-muted" />
            <h2 className="text-text font-semibold">Настройки генерации</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-text-muted hover:text-text hover:bg-surface-hover transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        <div className="p-5 space-y-5">
          {/* Provider tabs */}
          <div className="flex gap-2">
            <button
              onClick={() => { setTab('local'); update({ provider: 'local' }) }}
              className={`flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors border ${
                tab === 'local'
                  ? 'bg-primary/15 text-primary border-primary/30'
                  : 'bg-surface border-border text-text-muted hover:bg-surface-hover'
              }`}
            >
              <Server size={16} />
              LM Studio
            </button>
            <button
              onClick={() => { setTab('openai'); update({ provider: 'openai' }) }}
              className={`flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors border ${
                tab === 'openai'
                  ? 'bg-primary/15 text-primary border-primary/30'
                  : 'bg-surface border-border text-text-muted hover:bg-surface-hover'
              }`}
            >
              <Cloud size={16} />
              OpenAI API
            </button>
            <button
              onClick={() => setTab('comfyui')}
              className={`flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors border ${
                tab === 'comfyui'
                  ? 'bg-primary/15 text-primary border-primary/30'
                  : 'bg-surface border-border text-text-muted hover:bg-surface-hover'
              }`}
            >
              <Image size={16} />
              Изображения
            </button>
          </div>

          {/* Local settings */}
          {tab === 'local' && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-text mb-1.5">URL сервера</label>
                <input
                  type="text"
                  value={settings.localUrl}
                  onChange={(e) => update({ localUrl: e.target.value })}
                  placeholder="http://localhost:1234/v1"
                  className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-text text-sm placeholder:text-text-muted focus:outline-none focus:border-primary transition-colors"
                />
              </div>
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="block text-sm font-medium text-text">Модель</label>
                  <button
                    onClick={refreshModels}
                    disabled={modelsLoading}
                    className="flex items-center gap-1 text-xs text-text-muted hover:text-text transition-colors"
                  >
                    {modelsLoading ? (
                      <Loader2 size={12} className="animate-spin" />
                    ) : (
                      <RefreshCw size={12} />
                    )}
                    Обновить
                  </button>
                </div>

                {modelsError && (
                  <div className="flex items-center gap-2 px-3 py-2 bg-danger/10 border border-danger/30 rounded-lg mb-2">
                    <AlertCircle size={12} className="text-danger shrink-0" />
                    <span className="text-xs text-danger">{modelsError}</span>
                  </div>
                )}

                {modelsLoading && localModels.length === 0 ? (
                  <div className="flex items-center gap-2 px-3 py-2 bg-bg border border-border rounded-lg">
                    <Loader2 size={14} className="animate-spin text-text-muted" />
                    <span className="text-sm text-text-muted">Загрузка моделей...</span>
                  </div>
                ) : (
                  <select
                    value={settings.localModel}
                    onChange={(e) => update({ localModel: e.target.value })}
                    className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-text text-sm focus:outline-none focus:border-primary transition-colors"
                  >
                    {localModels.length === 0 && <option value="">Нет доступных моделей</option>}
                    {localModels.map((m) => (
                      <option key={m.id} value={m.id}>{m.name}</option>
                    ))}
                    <option value="custom">Другая (ввести вручную)</option>
                  </select>
                )}

                {settings.localModel === 'custom' && (
                  <input
                    type="text"
                    value=""
                    onChange={(e) => update({ localModel: e.target.value })}
                    placeholder="Название модели"
                    className="w-full px-3 py-2 mt-2 bg-bg border border-border rounded-lg text-text text-sm placeholder:text-text-muted focus:outline-none focus:border-primary transition-colors"
                  />
                )}

                {localModels.length > 0 && (
                  <p className="text-xs text-text-muted mt-1.5">
                    Загружено моделей: {localModels.length}
                  </p>
                )}
              </div>
              <div className="bg-bg rounded-lg p-3 flex items-start gap-2">
                <Monitor size={14} className="text-text-muted mt-0.5 shrink-0" />
                <p className="text-xs text-text-muted">
                  Убедитесь, что LM Studio запущен и модель загружена. Сервер автоматически обнаружит доступные модели.
                </p>
              </div>
            </div>
          )}

          {/* OpenAI settings */}
          {tab === 'openai' && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-text mb-1.5">API Key</label>
                <input
                  type="password"
                  value={settings.openaiKey}
                  onChange={(e) => update({ openaiKey: e.target.value })}
                  placeholder="sk-..."
                  className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-text text-sm placeholder:text-text-muted focus:outline-none focus:border-primary transition-colors"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-text mb-1.5">Модель</label>
                <select
                  value={settings.openaiModel}
                  onChange={(e) => update({ openaiModel: e.target.value })}
                  className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-text text-sm focus:outline-none focus:border-primary transition-colors"
                >
                  {OPENAI_MODELS.map((m) => (
                    <option key={m.id} value={m.id}>{m.name}</option>
                  ))}
                </select>
              </div>
              <div className="bg-bg rounded-lg p-3 flex items-start gap-2">
                <Cloud size={14} className="text-text-muted mt-0.5 shrink-0" />
                <p className="text-xs text-text-muted">
                  API ключ хранится только в localStorage и отправляется напрямую на сервер.
                </p>
              </div>
            </div>
          )}

          {/* ComfyUI / Image generation settings */}
          {tab === 'comfyui' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <label className="block text-sm font-medium text-text">Генерация изображений</label>
                <button
                  onClick={() => update({ imageGenerationEnabled: !settings.imageGenerationEnabled })}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                    settings.imageGenerationEnabled ? 'bg-primary' : 'bg-gray-300'
                  }`}
                >
                  <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    settings.imageGenerationEnabled ? 'translate-x-6' : 'translate-x-1'
                  }`} />
                </button>
              </div>

              {settings.imageGenerationEnabled && (
                <>
                  <div
                    className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm ${
                      comfyStatus === null
                        ? 'bg-bg border-border text-text-muted'
                        : comfyStatus.comfyui
                          ? 'bg-green-500/10 border-green-500/30 text-green-700'
                          : 'bg-danger/10 border-danger/30 text-danger'
                    }`}
                  >
                    <span
                      className={`w-2 h-2 rounded-full ${
                        comfyStatus === null ? 'bg-gray-400' : comfyStatus.comfyui ? 'bg-green-500' : 'bg-danger'
                      }`}
                    />
                    {comfyStatus === null
                      ? 'Проверка ComfyUI...'
                      : comfyStatus.comfyui
                        ? 'ComfyUI доступен'
                        : 'ComfyUI недоступен — будут использоваться стоковые изображения'}
                    {!comfyStatus?.npm && comfyStatus !== null && (
                      <span className="text-xs opacity-75">· npm не найден (Tailwind будет через CDN)</span>
                    )}
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-text mb-1.5">URL ComfyUI</label>
                    <input
                      type="text"
                      value={settings.comfyuiUrl}
                      onChange={(e) => update({ comfyuiUrl: e.target.value })}
                      placeholder="http://127.0.0.1:8188"
                      className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-text text-sm placeholder:text-text-muted focus:outline-none focus:border-primary transition-colors"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-text mb-1.5">Модель (checkpoint)</label>
                    <input
                      type="text"
                      value={settings.comfyuiModel}
                      onChange={(e) => update({ comfyuiModel: e.target.value })}
                      placeholder="model.safetensors"
                      className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-text text-sm placeholder:text-text-muted focus:outline-none focus:border-primary transition-colors"
                    />
                    <p className="text-xs text-text-muted mt-1">Имя файла модели в папке checkpoints ComfyUI</p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-text mb-1.5">Путь к воркфлоу (JSON)</label>
                    <input
                      type="text"
                      value={settings.comfyuiWorkflowPath}
                      onChange={(e) => update({ comfyuiWorkflowPath: e.target.value })}
                      placeholder="C:\Users\you\ComfyUI\workflows\my_txt2img.json"
                      className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-text text-sm placeholder:text-text-muted focus:outline-none focus:border-primary transition-colors"
                    />
                    <p className="text-xs text-text-muted mt-1">
                      Путь должен быть внутри разрешённого каталога (COMFYUI_WORKFLOWS_ROOT в .env). Поддерживаются UI- и API-формат экспорта. Если пусто — встроенный шаблон.
                    </p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-text mb-1.5">
                      Шаги генерации: <span className="text-primary font-bold">{settings.imageSteps}</span>
                    </label>
                    <input
                      type="range"
                      min={1}
                      max={50}
                      value={settings.imageSteps}
                      onChange={(e) => update({ imageSteps: Number(e.target.value) })}
                      className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-primary"
                    />
                    <div className="flex justify-between text-xs text-text-muted mt-1">
                      <span>1 (быстро)</span>
                      <span>25</span>
                      <span>50 (качество)</span>
                    </div>
                  </div>

                  <div className="bg-bg rounded-lg p-3 flex items-start gap-2">
                    <Image size={14} className="text-text-muted mt-0.5 shrink-0" />
                    <div className="text-xs text-text-muted">
                      <p className="mb-1">Воркфлоу должен содержать ноды:</p>
                      <ul className="list-disc list-inside space-y-0.5 text-text-muted/80">
                        <li>CheckpointLoaderSimple</li>
                        <li>CLIPTextEncode (positive + negative)</li>
                        <li>EmptyLatentImage</li>
                        <li>KSampler</li>
                        <li>VAEDecode</li>
                        <li>SaveImage</li>
                      </ul>
                      <p className="mt-1.5">LLM будет автоматически подставлять промпт, размер и параметры сэмплинга.</p>
                    </div>
                  </div>
                </>
              )}
            </div>
          )}
        </div>

        <div className="px-5 py-3 border-t border-border flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-primary hover:bg-primary-hover text-white rounded-lg text-sm font-medium transition-colors"
          >
            Готово
          </button>
        </div>
      </div>
    </div>
  )
}
