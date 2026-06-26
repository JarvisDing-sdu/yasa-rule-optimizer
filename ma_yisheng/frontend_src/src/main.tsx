import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { ErrorBoundary } from './components/ErrorBoundary.tsx'

window.addEventListener('error', (event) => {
  window.maYisheng?.log?.(`error: ${event.message} ${event.filename}:${event.lineno}:${event.colno}`)
})

window.addEventListener('unhandledrejection', (event) => {
  const reason = event.reason instanceof Error ? event.reason.stack || event.reason.message : String(event.reason)
  window.maYisheng?.log?.(`unhandledrejection: ${reason}`)
})

const root = document.getElementById('root')
if (!root) {
  window.maYisheng?.log?.('missing #root element')
  throw new Error('missing #root element')
}

window.maYisheng?.log?.('renderer boot')

createRoot(root).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
)
