import axios from 'axios'
import type { GenerateRequest, GenerateResponse, GenerationInfo, Landing, LandingDetail, PaginatedResponse, SectionSummary, Skill } from '../types'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

export async function getLandings(page = 1, pageSize = 12, search = '', mine = false): Promise<PaginatedResponse<Landing>> {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  if (search) params.set('search', search)
  if (mine) params.set('mine', 'true')
  const { data } = await api.get(`/landings?${params}`)
  return data
}

export async function getLanding(id: string): Promise<LandingDetail> {
  const { data } = await api.get(`/landings/${id}`)
  return data
}

export async function getLandingHtml(id: string): Promise<string> {
  const { data } = await api.get(`/landings/${id}/html`, { responseType: 'text' })
  return data
}

export async function getLandingCss(id: string): Promise<string | null> {
  try {
    const { data } = await api.get(`/landings/${id}/css`, { responseType: 'text' })
    return data
  } catch {
    return null
  }
}

export async function downloadLanding(id: string): Promise<Blob> {
  const { data } = await api.get(`/landings/${id}/download`, { responseType: 'blob' })
  return data
}

export async function generateLanding(req: GenerateRequest): Promise<GenerateResponse> {
  const formData = new FormData()
  formData.append('prompt', req.prompt)
  if (req.title) formData.append('title', req.title)
  if (req.tags) formData.append('tags', JSON.stringify(req.tags))
  if (req.brandbook) formData.append('brandbook', req.brandbook)
  formData.append('provider', req.provider)
  formData.append('model', req.model)
  if (req.apiEndpoint) formData.append('api_endpoint', req.apiEndpoint)
  if (req.apiKey) formData.append('api_key', req.apiKey)
  formData.append('skill_ids', JSON.stringify(req.skillIds))
  if (req.comfyuiWorkflowPath) formData.append('comfyui_workflow_path', req.comfyuiWorkflowPath)
  if (req.comfyuiUrl) formData.append('comfyui_url', req.comfyuiUrl)
  if (req.workflow) formData.append('workflow', req.workflow)
  if (req.imageSteps != null) formData.append('image_steps', String(req.imageSteps))
  formData.append('use_llm_markup', String(req.useLlmMarkup ?? false))
  const { data } = await api.post('/generate', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function getSkills(): Promise<Skill[]> {
  const { data } = await api.get('/skills')
  return data
}

export async function createSkill(skill: { name: string; description: string; prompt_addition: string }): Promise<Skill> {
  const { data } = await api.post('/skills', skill)
  return data
}

export async function updateSkill(id: string, skill: { name: string; description: string; prompt_addition: string }): Promise<Skill> {
  const { data } = await api.put(`/skills/${id}`, skill)
  return data
}

export async function deleteSkill(id: string): Promise<void> {
  await api.delete(`/skills/${id}`)
}

export async function deleteLanding(id: string): Promise<void> {
  await api.delete(`/landings/${id}`)
}

export async function updateLanding(id: string, data: { title?: string; tags?: string[] }): Promise<Landing> {
  const { data: result } = await api.put(`/landings/${id}`, data)
  return result
}

export async function getLandingSections(id: string): Promise<SectionSummary[]> {
  const { data } = await api.get(`/landings/${id}/sections`)
  return data
}

export async function getGenerationInfo(id: string): Promise<GenerationInfo> {
  const { data } = await api.get(`/landings/${id}/generation`)
  return data
}

export async function regenerateLandingImage(id: string, sectionType: string, itemIndex?: number): Promise<void> {
  await api.post(`/landings/${id}/regenerate-image`, { section_type: sectionType, item_index: itemIndex ?? null }, { timeout: 600000 })
}

export async function regenerateLandingSection(id: string, sectionType: string): Promise<void> {
  await api.post(`/landings/${id}/regenerate-section`, { section_type: sectionType }, { timeout: 180000 })
}

export async function publishLanding(id: string, published: boolean): Promise<Landing> {
  const { data } = await api.post(`/landings/${id}/publish`, { published })
  return data
}

export async function checkComfyui(url: string): Promise<{ ok: boolean; error?: string; checkpoints?: string[] }> {
  const { data } = await api.post('/comfyui/check', { url }, { timeout: 20000 })
  return data
}

export default api
