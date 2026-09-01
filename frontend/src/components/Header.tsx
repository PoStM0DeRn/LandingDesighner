import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Settings, Sparkles, LogIn, LogOut, UserCircle } from 'lucide-react'
import SettingsModal from './SettingsModal'
import SkillsManager from './SkillsManager'
import AuthModal from './AuthModal'
import { useAuth } from '../hooks/useAuth'

export default function Header() {
  const location = useLocation()
  const [showSettings, setShowSettings] = useState(false)
  const [showSkills, setShowSkills] = useState(false)
  const { user, logout, authModalOpen, openAuthModal, closeAuthModal } = useAuth()

  return (
    <>
      <header className="border-b border-border sticky top-0 z-50 bg-bg/80 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <Link to="/" className="flex items-center gap-3 no-underline">
              <div className="w-9 h-9 rounded-lg bg-primary flex items-center justify-center text-white font-bold text-lg">
                L
              </div>
              <span className="text-text font-semibold text-lg hidden sm:block">
                Landing Generator
              </span>
            </Link>

            <nav className="flex items-center gap-1">
              <Link
                to="/"
                className={`px-4 py-2 rounded-lg text-sm font-medium no-underline transition-colors ${
                  location.pathname === '/'
                    ? 'bg-primary/15 text-primary'
                    : 'text-text-muted hover:text-text hover:bg-surface-hover'
                }`}
              >
                Витрина
              </Link>
              <Link
                to="/generate"
                className={`px-4 py-2 rounded-lg text-sm font-medium no-underline transition-colors ${
                  location.pathname === '/generate'
                    ? 'bg-primary/15 text-primary'
                    : 'text-text-muted hover:text-text hover:bg-surface-hover'
                }`}
              >
                Генерация
              </Link>
              <button
                onClick={() => setShowSkills(true)}
                className="p-2 rounded-lg text-text-muted hover:text-text hover:bg-surface-hover transition-colors"
                title="Скиллы"
              >
                <Sparkles size={18} />
              </button>
              <button
                onClick={() => setShowSettings(true)}
                className="p-2 rounded-lg text-text-muted hover:text-text hover:bg-surface-hover transition-colors"
                title="Настройки"
              >
                <Settings size={18} />
              </button>
              {user ? (
                <div className="flex items-center gap-1 ml-1 pl-1 border-l border-border">
                  <span
                    className="flex items-center gap-1.5 text-sm text-text px-2 py-1.5"
                    title={`Вы вошли как ${user.nickname}`}
                  >
                    <UserCircle size={18} className="text-primary" />
                    <span className="hidden sm:inline">{user.nickname}</span>
                  </span>
                  <button
                    onClick={logout}
                    className="p-2 rounded-lg text-text-muted hover:text-danger hover:bg-danger/10 transition-colors"
                    title="Выйти"
                  >
                    <LogOut size={16} />
                  </button>
                </div>
              ) : (
                <button
                  onClick={openAuthModal}
                  className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-sm font-medium bg-primary/15 text-primary hover:bg-primary/25 transition-colors ml-1"
                >
                  <LogIn size={15} />
                  Войти
                </button>
              )}
            </nav>
          </div>
        </div>
      </header>

      {showSettings && <SettingsModal onClose={() => setShowSettings(false)} />}
      {showSkills && <SkillsManager onClose={() => setShowSkills(false)} />}
      {authModalOpen && <AuthModal onClose={closeAuthModal} />}
    </>
  )
}
