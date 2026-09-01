import { useEffect, useState } from 'react'
import { X, Plus, Pencil, Trash2, Loader2, AlertCircle } from 'lucide-react'
import { getSkills, createSkill, updateSkill, deleteSkill } from '../api/client'
import type { Skill } from '../types'

interface SkillsManagerProps {
  onClose: () => void
}

export default function SkillsManager({ onClose }: SkillsManagerProps) {
  const [skills, setSkills] = useState<Skill[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState<Skill | null>(null)
  const [form, setForm] = useState({ name: '', description: '', prompt_addition: '' })
  const [saving, setSaving] = useState(false)

  const load = () => {
    setLoading(true)
    getSkills()
      .then(setSkills)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const resetForm = () => {
    setForm({ name: '', description: '', prompt_addition: '' })
    setEditing(null)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.name.trim() || !form.prompt_addition.trim()) return
    setSaving(true)
    try {
      if (editing) {
        await updateSkill(editing.id, form)
      } else {
        await createSkill(form)
      }
      resetForm()
      load()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const handleEdit = (skill: Skill) => {
    setEditing(skill)
    setForm({ name: skill.name, description: skill.description, prompt_addition: skill.prompt_addition })
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Удалить скилл?')) return
    try {
      await deleteSkill(id)
      load()
    } catch (e: any) {
      setError(e.message)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-800/40 backdrop-blur-sm p-4">
      <div className="bg-surface rounded-2xl border border-border w-full max-w-2xl max-h-[90vh] flex flex-col overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border shrink-0">
          <h2 className="text-text font-semibold">Управление скиллами</h2>
          <button onClick={onClose} className="p-1.5 rounded-lg text-text-muted hover:text-text hover:bg-surface-hover transition-colors">
            <X size={16} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {error && (
            <div className="bg-danger/10 border border-danger/30 rounded-lg p-3 flex items-center gap-2">
              <AlertCircle size={14} className="text-danger shrink-0" />
              <span className="text-danger text-sm">{error}</span>
              <button onClick={() => setError(null)} className="ml-auto text-danger"><X size={14} /></button>
            </div>
          )}

          <form onSubmit={handleSubmit} className="bg-bg rounded-xl p-4 space-y-3 border border-border">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-sm font-medium text-text">{editing ? 'Редактировать' : 'Новый скилл'}</span>
              {editing && (
                <button type="button" onClick={resetForm} className="text-xs text-text-muted hover:text-text">Отмена</button>
              )}
            </div>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="Название"
              className="w-full px-3 py-2 bg-surface border border-border rounded-lg text-text text-sm placeholder:text-text-muted focus:outline-none focus:border-primary"
              required
            />
            <input
              type="text"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              placeholder="Описание (опционально)"
              className="w-full px-3 py-2 bg-surface border border-border rounded-lg text-text text-sm placeholder:text-text-muted focus:outline-none focus:border-primary"
            />
            <textarea
              value={form.prompt_addition}
              onChange={(e) => setForm({ ...form, prompt_addition: e.target.value })}
              placeholder="Инструкция для LLM (что добавить в промпт)"
              rows={3}
              className="w-full px-3 py-2 bg-surface border border-border rounded-lg text-text text-sm placeholder:text-text-muted focus:outline-none focus:border-primary resize-none"
              required
            />
            <button
              type="submit"
              disabled={saving || !form.name.trim() || !form.prompt_addition.trim()}
              className="inline-flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary-hover text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
            >
              {saving ? <Loader2 size={14} className="animate-spin" /> : editing ? <Pencil size={14} /> : <Plus size={14} />}
              {editing ? 'Сохранить' : 'Добавить'}
            </button>
          </form>

          {loading ? (
            <div className="flex justify-center py-8"><Loader2 className="animate-spin text-primary" /></div>
          ) : skills.length === 0 ? (
            <p className="text-center text-text-muted py-8">Нет скиллов</p>
          ) : (
            <div className="space-y-2">
              {skills.map((skill) => (
                <div key={skill.id} className="bg-bg rounded-xl p-4 border border-border flex items-start gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-text text-sm">{skill.name}</span>
                      {skill.built_in && (
                        <span className="text-xs bg-primary/10 text-primary px-1.5 py-0.5 rounded">встроенный</span>
                      )}
                    </div>
                    {skill.description && (
                      <p className="text-xs text-text-muted mt-0.5">{skill.description}</p>
                    )}
                    <p className="text-xs text-text-muted/70 mt-1 truncate">{skill.prompt_addition}</p>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    <button
                      onClick={() => handleEdit(skill)}
                      className="p-1.5 rounded-lg text-text-muted hover:text-text hover:bg-surface-hover transition-colors"
                    >
                      <Pencil size={14} />
                    </button>
                    {!skill.built_in && (
                      <button
                        onClick={() => handleDelete(skill.id)}
                        className="p-1.5 rounded-lg text-text-muted hover:text-danger hover:bg-danger/10 transition-colors"
                      >
                        <Trash2 size={14} />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="px-5 py-3 border-t border-border flex justify-end shrink-0">
          <button onClick={onClose} className="px-4 py-2 bg-primary hover:bg-primary-hover text-white rounded-lg text-sm font-medium transition-colors">
            Готово
          </button>
        </div>
      </div>
    </div>
  )
}
