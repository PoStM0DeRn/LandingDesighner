export default function Footer() {
  return (
    <footer className="border-t border-border mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="text-text-muted text-sm">
            AI Landing Generator &mdash; Powered by LangGraph &amp; V100
          </p>
          <div className="flex items-center gap-4 text-text-muted text-sm">
            <span>v0.1.0</span>
          </div>
        </div>
      </div>
    </footer>
  )
}
