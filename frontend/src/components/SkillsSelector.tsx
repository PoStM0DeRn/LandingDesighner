import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { getSkills } from '../api/client'
import type { Skill } from '../types'

interface SkillsSelectorProps {
  selected: string[]
  onChange: (ids: string[]) => void
}

export default function SkillsSelector({ selected, onChange }: SkillsSelectorProps) {
  const [skills, setSkills] = useState<Skill[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getSkills()
      .then(setSkills)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const toggle = (id: string) => {
    if (selected.includes(id)) {
      onChange(selected.filter((s) => s !== id))
    } else {
      onChange([...selected, id])
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-text-muted text-sm">
        <Loader2 size={14} className="animate-spin" />
        Загрузка скиллов...
      </div>
    )
  }

  if (skills.length === 0) {
    return (
      <p className="text-text-muted text-sm">Нет доступных скиллов</p>
    )
  }

  return (
    <div className="flex flex-wrap gap-2">
      {skills.map((skill) => {
        const active = selected.includes(skill.id)
        return (
          <button
            key={skill.id}
            type="button"
            onClick={() => toggle(skill.id)}
            title={skill.description}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium border transition-colors cursor-pointer ${
              active
                ? 'bg-primary/15 text-primary border-primary/30'
                : 'bg-surface border-border text-text-muted hover:bg-surface-hover hover:text-text'
            }`}
          >
            {active && <span className="text-xs">✓</span>}
            {skill.name}
          </button>
        )
      })}
    </div>
  )
}
