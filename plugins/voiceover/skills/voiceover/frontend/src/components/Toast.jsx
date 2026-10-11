import { createContext, useCallback, useContext, useRef, useState } from 'react'
import { Info, CheckCircle2, AlertTriangle, X } from 'lucide-react'

const ToastCtx = createContext(null)

export function useToast() {
  const ctx = useContext(ToastCtx)
  if (!ctx) throw new Error('useToast must be used within <ToastProvider>')
  return ctx
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const idRef = useRef(0)

  const dismiss = useCallback((id) => {
    setToasts((t) => t.filter((x) => x.id !== id))
  }, [])

  const push = useCallback(
    (message, tone = 'info', ttl = 4200) => {
      const id = ++idRef.current
      setToasts((t) => [...t, { id, message, tone }])
      if (ttl) setTimeout(() => dismiss(id), ttl)
      return id
    },
    [dismiss]
  )

  const toast = {
    info: (m) => push(m, 'info'),
    success: (m) => push(m, 'success'),
    error: (m) => push(m, 'error', 6000),
  }

  const toneStyles = {
    info: 'border-line bg-white text-slate',
    success: 'border-green-200 bg-green-50 text-green-800',
    error: 'border-red-200 bg-red-50 text-red-700',
  }
  const ToneIcon = { info: Info, success: CheckCircle2, error: AlertTriangle }

  return (
    <ToastCtx.Provider value={toast}>
      {children}
      <div className="fixed bottom-5 right-5 z-50 flex w-80 max-w-[calc(100vw-2.5rem)] flex-col gap-2">
        {toasts.map((t) => {
          const Icon = ToneIcon[t.tone] || Info
          return (
            <div
              key={t.id}
              className={`animate-fadein flex items-start gap-2 rounded-xl border px-4 py-3 text-sm shadow-lg ${toneStyles[t.tone]}`}
              role="status"
            >
              <Icon className="mt-0.5 h-4 w-4 flex-shrink-0" aria-hidden="true" />
              <span className="flex-1 break-words">{t.message}</span>
              <button
                onClick={() => dismiss(t.id)}
                className="text-muted hover:text-slate"
                aria-label="Dismiss"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          )
        })}
      </div>
    </ToastCtx.Provider>
  )
}
