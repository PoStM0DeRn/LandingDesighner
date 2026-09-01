import { useState } from 'react'
import { X, LogIn, UserPlus, Loader2 } from 'lucide-react'
import { useAuth } from '../hooks/useAuth'

interface AuthModalProps {
  onClose: () => void
}

export default function AuthModal({ onClose }: AuthModalProps) {
  const { login, register } = useAuth()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [nickname, setNickname] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!nickname.trim() || !password) return
    setBusy(true)
    setError(null)
    try {
      if (mode === 'login') await login(nickname.trim(), password)
      else await register(nickname.trim(), password)
      onClose()
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail || 'Что-то пошло не так')
    } finally {
      setBusy(false)
    }
  }

  const tabCls = (active: boolean) =>
    `flex-1 px-4 py-2 rounded-lg text-sm font-medium transition-colors border ${
      active
        ? 'bg-primary/15 text-primary border-primary/30'
        : 'bg-surface border-border text-text-muted hover:bg-surface-hover'
    }`

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-800/40 backdrop-blur-sm p-4">
      <div className="bg-surface rounded-2xl border border-border w-full max-w-sm overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h2 className="text-text font-semibold">
            {mode === 'login' ? 'Вход' : 'Регистрация'}
          </h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-text-muted hover:text-text hover:bg-surface-hover transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        <form onSubmit={submit} className="p-5 space-y-4">
          <div className="flex gap-2">
            <button type="button" onClick={() => setMode('login')} className={tabCls(mode === 'login')}>
              Вход
            </button>
            <button type="button" onClick={() => setMode('register')} className={tabCls(mode === 'register')}>
              Регистрация
            </button>
          </div>

          <div>
            <label className="block text-sm font-medium text-text mb-1.5">Никнейм</label>
            <input
              type="text"
              value={nickname}
              onChange={(e) => setNickname(e.target.value)}
              placeholder="3-32 символа: латиница, цифры, - _"
              className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-text text-sm placeholder:text-text-muted focus:outline-none focus:border-primary transition-colors"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-text mb-1.5">Пароль</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Минимум 6 символов"
              className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-text text-sm placeholder:text-text-muted focus:outline-none focus:border-primary transition-colors"
              required
            />
          </div>

          {error && (
            <div className="px-3 py-2 bg-danger/10 border border-danger/30 rounded-lg text-xs text-danger">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={busy || !nickname.trim() || !password}
            className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-primary hover:bg-primary-hover text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {busy ? (
              <Loader2 size={16} className="animate-spin" />
            ) : mode === 'login' ? (
              <LogIn size={16} />
            ) : (
              <UserPlus size={16} />
            )}
            {mode === 'login' ? 'Войти' : 'Создать аккаунт'}
          </button>

          <p className="text-xs text-text-muted text-center">
            {mode === 'register'
              ? 'Никнейм будет виден на витрине рядом с вашими работами.'
              : 'Вход нужен, чтобы генерировать лендинги.'}
          </p>
        </form>
      </div>
    </div>
  )
}
