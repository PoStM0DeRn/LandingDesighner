import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { SettingsProvider } from './hooks/useSettings'
import { AuthProvider } from './hooks/useAuth'
import Header from './components/Header'
import Footer from './components/Footer'
import CatalogPage from './pages/CatalogPage'
import LandingDetailPage from './pages/LandingDetailPage'
import GeneratePage from './pages/GeneratePage'
import NotFoundPage from './pages/NotFoundPage'

export default function App() {
  return (
    <AuthProvider>
      <SettingsProvider>
        <BrowserRouter>
          <div className="min-h-screen flex flex-col">
            <Header />
            <main className="flex-1">
              <Routes>
                <Route path="/" element={<CatalogPage />} />
                <Route path="/landing/:id" element={<LandingDetailPage />} />
                <Route path="/generate" element={<GeneratePage />} />
                <Route path="*" element={<NotFoundPage />} />
              </Routes>
            </main>
            <Footer />
          </div>
        </BrowserRouter>
      </SettingsProvider>
    </AuthProvider>
  )
}
