import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import axios from 'axios'

export type LLMProvider = 'local' | 'openai'

export interface Settings {
  provider: LLMProvider
  localUrl: string
  localModel: string
  openaiKey: string
  openaiModel: string
  comfyuiUrl: string
  comfyuiModel: string
  comfyuiWorkflowPath: string
  imageGenerationEnabled: boolean
  imageSteps: number
}

const defaults: Settings = {
  provider: 'local',
  localUrl: 'http://localhost:1234/v1',
  localModel: '',
  openaiKey: '',
  openaiModel: 'gpt-4o',
  comfyuiUrl: 'http://127.0.0.1:8188',
  comfyuiModel: '',
  comfyuiWorkflowPath: '',
  imageGenerationEnabled: true,
  imageSteps: 8,
}

export interface ModelItem {
  id: string
  name: string
}

interface SettingsCtx {
  settings: Settings
  update: (partial: Partial<Settings>) => void
  localModels: ModelItem[]
  modelsLoading: boolean
  modelsError: string | null
  refreshModels: () => void
}

const SettingsContext = createContext<SettingsCtx>({
  settings: defaults,
  update: () => {},
  localModels: [],
  modelsLoading: false,
  modelsError: null,
  refreshModels: () => {},
})

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<Settings>(() => {
    try {
      const saved = localStorage.getItem('lg-settings')
      return saved ? { ...defaults, ...JSON.parse(saved) } : defaults
    } catch {
      return defaults
    }
  })

  const [localModels, setLocalModels] = useState<ModelItem[]>([])
  const [modelsLoading, setModelsLoading] = useState(false)
  const [modelsError, setModelsError] = useState<string | null>(null)

  const fetchModels = useCallback(async () => {
    setModelsLoading(true)
    setModelsError(null)
    try {
      const { data } = await axios.get('/api/models', { params: { url: settings.localUrl } })
      const models: ModelItem[] = data.models || []
      setLocalModels(models)
      if (models.length > 0 && !models.find((m) => m.id === settings.localModel)) {
        setSettings((prev) => ({ ...prev, localModel: models[0].id }))
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to fetch models'
      setModelsError(msg)
      setLocalModels([])
    } finally {
      setModelsLoading(false)
    }
  }, [settings.localUrl])

  useEffect(() => {
    localStorage.setItem('lg-settings', JSON.stringify(settings))
  }, [settings])

  useEffect(() => {
    fetchModels()
  }, [settings.localUrl])

  const update = (partial: Partial<Settings>) => setSettings((prev) => ({ ...prev, ...partial }))

  return (
    <SettingsContext.Provider value={{ settings, update, localModels, modelsLoading, modelsError, refreshModels: fetchModels }}>
      {children}
    </SettingsContext.Provider>
  )
}

export function useSettings() {
  return useContext(SettingsContext)
}

export const OPENAI_MODELS = [
  { id: 'gpt-4o', name: 'GPT-4o' },
  { id: 'gpt-4o-mini', name: 'GPT-4o Mini' },
  { id: 'gpt-4-turbo', name: 'GPT-4 Turbo' },
  { id: 'gpt-3.5-turbo', name: 'GPT-3.5 Turbo' },
]
