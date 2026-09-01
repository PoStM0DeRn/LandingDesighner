export interface Landing {
  id: string
  title: string
  description: string
  prompt: string
  created_at: string
  updated_at: string
  thumbnail_url?: string
  tags: string[]
  status: 'ready' | 'generating' | 'error'
  error_message?: string | null
  provider?: string | null
  model?: string | null
  owner_nickname?: string | null
  published?: boolean | null
}

export interface LandingDetail extends Landing {
  html: string
  css: string
}

export interface Skill {
  id: string
  name: string
  description: string
  prompt_addition: string
  built_in: boolean
}

export interface GenerateRequest {
  prompt: string
  title?: string
  tags?: string[]
  brandbook?: File
  provider: 'local' | 'openai'
  model: string
  apiEndpoint?: string
  apiKey?: string
  skillIds: string[]
  comfyuiWorkflowPath?: string
  comfyuiUrl?: string
  workflow?: File
  imageSteps?: number
  useLlmMarkup?: boolean
}

export interface GenerateResponse {
  id: string
  status: 'generating' | 'ready'
  message: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface GenerationProgress {
  stage: string
  message: string
  images_done: number
  images_total: number
  done?: boolean
  status?: string
  error?: string
}

export interface SectionSummary {
  index: number
  type: string
  title: string
  items: number
  item_titles?: string[]
  has_image: boolean
}

export interface GenerationSkillInfo {
  name: string
  description: string
  prompt_addition: string
}

export interface GenerationInfo {
  available: boolean
  provider: string | null
  model: string | null
  prompt: string
  use_llm_markup: boolean
  image_steps: number | null
  comfyui_workflow_path: string | null
  comfyui_url: string | null
  intent: {
    topic?: string
    style?: string
    tone?: string
    target_audience?: string
  } | null
  tokens: {
    primary_color?: string
    secondary_color?: string
    accent_color?: string
    bg_color?: string
    text_color?: string
    heading_font?: string
    body_font?: string
  } | null
  skills: GenerationSkillInfo[]
}
