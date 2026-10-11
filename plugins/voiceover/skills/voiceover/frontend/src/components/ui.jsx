// Small, cohesive UI primitives shared across the app.
import { AlertTriangle, Copy, FileDiff } from 'lucide-react'
import { STATE_LABELS, describeReview } from '../constants'

export function Button({
  children,
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled,
  className = '',
  ...props
}) {
  const base =
    'inline-flex items-center justify-center gap-2 font-semibold rounded-lg transition duration-150 active:scale-[.98] focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/40 disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100'
  const sizes = {
    sm: 'text-xs px-3 py-1.5',
    md: 'text-sm px-4 py-2',
    lg: 'text-sm px-5 py-2.5',
  }
  const variants = {
    primary: 'bg-brand-600 text-white shadow-xs hover:bg-brand-700',
    amber: 'bg-accent-500 text-navy shadow-xs hover:bg-accent-600',
    ghost: 'bg-transparent text-brand-700 border border-brand-200 hover:bg-brand-50',
    subtle: 'bg-white text-slate border border-line hover:bg-slate-50',
    danger: 'bg-white text-red-600 border border-red-200 hover:bg-red-50',
  }
  return (
    <button
      className={`${base} ${sizes[size]} ${variants[variant]} ${className}`}
      disabled={disabled || loading}
      {...props}
    >
      {loading && <Spinner />}
      {children}
    </button>
  )
}

export function Spinner({ className = '' }) {
  return (
    <svg
      className={`animate-spin h-4 w-4 ${className}`}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-90"
        fill="currentColor"
        d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
      />
    </svg>
  )
}

export function Card({ children, className = '' }) {
  return (
    <div
      className={`bg-white border border-slate-200/60 rounded-2xl shadow-sm ${className}`}
    >
      {children}
    </div>
  )
}

export function Field({ label, hint, children }) {
  return (
    <label className="block">
      <div className="flex items-baseline justify-between mb-1.5">
        <span className="text-sm font-semibold text-navy">{label}</span>
        {hint && <span className="text-xs text-muted">{hint}</span>}
      </div>
      {children}
    </label>
  )
}

export const inputClass =
  'w-full rounded-lg border border-line bg-white px-3 py-2 text-sm text-slate placeholder:text-muted focus:outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 transition'

export function StatePill({ state, stale }) {
  const [cls, label] = STATE_LABELS[state] || [
    'bg-slate-100 text-slate-600',
    state,
  ]
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className={`text-[0.68rem] font-bold uppercase tracking-wide px-2 py-0.5 rounded-full ${cls}`}
      >
        {label}
      </span>
      {stale && (
        <span className="text-[0.68rem] font-bold uppercase tracking-wide px-2 py-0.5 rounded-full bg-amber-100 text-amber-700">
          Needs regenerating
        </span>
      )}
    </span>
  )
}

// A labelled progress bar driven by an SSE event {stage,done,total,message}.
export function ProgressBar({ progress, tone = 'blue' }) {
  const total = progress?.total || 0
  const done = progress?.done || 0
  const pct = total > 0 ? Math.min(100, Math.round((done / total) * 100)) : null
  const barTone = tone === 'amber' ? 'bg-accent-500' : 'bg-brand-600'
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs text-muted">
        <span className="font-medium text-slate">
          {progress?.message || progress?.stage || 'Working…'}
        </span>
        {total > 0 && (
          <span className="tabular-nums">
            {done} / {total}
          </span>
        )}
      </div>
      <div className="relative h-2.5 w-full overflow-hidden rounded-full bg-slate-100">
        {pct === null ? (
          <div className={`shimmer absolute inset-0 ${barTone} opacity-70`} />
        ) : (
          <div
            className={`h-full rounded-full ${barTone} transition-all duration-300`}
            style={{ width: `${pct}%` }}
          />
        )}
      </div>
    </div>
  )
}

// A row of per-slide tick marks that fill as a job progresses.
export function SlideTicks({ total, done }) {
  if (!total) return null
  return (
    <div className="flex flex-wrap gap-1">
      {Array.from({ length: total }).map((_, i) => (
        <span
          key={i}
          className={`h-1.5 w-4 rounded-full transition-colors ${
            i < done ? 'bg-brand-600' : 'bg-slate-200'
          }`}
        />
      ))}
    </div>
  )
}

export function ErrorBanner({ message, onRetry }) {
  if (!message) return null
  return (
    <div className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
      <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0" aria-hidden="true" />
      <div className="flex-1">
        <p className="font-semibold">Something went wrong</p>
        <p className="text-red-600/90 whitespace-pre-wrap break-words">{message}</p>
      </div>
      {onRetry && (
        <Button variant="danger" size="sm" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  )
}

// What the last re-uploaded PDF did to the deck, above the narration editor.
export function ReviewSummary({ review, children }) {
  if (!review?.total) return null
  return (
    <div className="rounded-xl border border-brand-200 bg-brand-50/60 px-4 py-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <FileDiff
            className="mt-0.5 h-4 w-4 flex-shrink-0 text-brand-700"
            aria-hidden="true"
          />
          <div className="text-sm">
            <p className="font-semibold text-navy">
              New PDF — {describeReview(review)}
            </p>
            <p className="mt-0.5 text-muted">
              {review.unchanged} slide{review.unchanged === 1 ? '' : 's'} kept
              their narration and their audio. Flagged slides keep the old script
              as a starting point — ask Claude to redraft them, or edit them here.
            </p>
            {review.suspect_rerender && (
              <p className="mt-1.5 text-amber-700">
                Most slides came back with the same words but a different
                rendering, which usually means the PDF was re-exported rather
                than rewritten. Check a flagged slide before redrafting the
                whole deck.
              </p>
            )}
          </div>
        </div>
        {children}
      </div>
    </div>
  )
}

export function CopyButton({ value, label = 'Copy' }) {
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value)
    } catch {
      /* clipboard blocked — no-op */
    }
  }
  return (
    <Button variant="subtle" size="sm" onClick={copy}>
      <Copy className="h-4 w-4" /> {label}
    </Button>
  )
}
