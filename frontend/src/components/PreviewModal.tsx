import { X, Download, Copy, ExternalLink } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

interface PreviewModalProps {
  html: string
  title: string
  landingId: string
  onClose: () => void
}

export default function PreviewModal({ html, title, landingId, onClose }: PreviewModalProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleEsc)
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', handleEsc)
      document.body.style.overflow = ''
    }
  }, [onClose])

  useEffect(() => {
    if (iframeRef.current) {
      const doc = iframeRef.current.contentDocument
      if (doc) {
        doc.open()
        doc.write(html)
        doc.close()
      }
    }
  }, [html])

  const handleCopy = async () => {
    await navigator.clipboard.writeText(html)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleOpenTab = () => {
    const blob = new Blob([html], { type: 'text/html' })
    const url = URL.createObjectURL(blob)
    window.open(url, '_blank')
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-800/40 backdrop-blur-sm p-4">
      <div className="bg-surface rounded-2xl border border-border w-full max-w-6xl h-[90vh] flex flex-col overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <h2 className="text-text font-semibold truncate">{title}</h2>
          <div className="flex items-center gap-2">
            <button
              onClick={handleCopy}
              className="p-2 rounded-lg text-text-muted hover:text-text hover:bg-surface-hover transition-colors"
              title="Копировать HTML"
            >
              <Copy size={16} />
            </button>
            <button
              onClick={handleOpenTab}
              className="p-2 rounded-lg text-text-muted hover:text-text hover:bg-surface-hover transition-colors"
              title="Открыть в новой вкладке"
            >
              <ExternalLink size={16} />
            </button>
            <a
              href={`/api/landings/${landingId}/download`}
              className="p-2 rounded-lg text-text-muted hover:text-accent hover:bg-accent/10 transition-colors no-underline"
              title="Скачать ZIP"
            >
              <Download size={16} />
            </a>
            <button
              onClick={onClose}
              className="p-2 rounded-lg text-text-muted hover:text-danger hover:bg-danger/10 transition-colors"
            >
              <X size={16} />
            </button>
          </div>
        </div>
        {copied && (
          <div className="px-4 py-2 bg-success/10 text-success text-sm text-center">
            HTML скопирован в буфер обмена
          </div>
        )}
        <div className="flex-1 bg-white m-2 rounded-lg overflow-hidden">
          <iframe
            ref={iframeRef}
            className="w-full h-full border-0"
            title={title}
            sandbox="allow-scripts allow-same-origin"
          />
        </div>
      </div>
    </div>
  )
}
