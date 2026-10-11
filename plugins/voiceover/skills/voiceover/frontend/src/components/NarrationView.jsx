import { useCallback, useEffect, useRef, useState } from 'react'
import { ArrowLeft, ArrowRight, Check } from 'lucide-react'
import { api, toRel } from '../api'
import { CHANGE_LABELS, estimateSeconds, formatDuration } from '../constants'
import DraftStatus from './DraftStatus'
import { useToast } from './Toast'
import { Button, ReviewSummary, Spinner } from './ui'

const AUTOSAVE_MS = 900

// The narration screen: thumbnails across the top, the slide on the left, its
// script on the right. Edits autosave a slide at a time.
//
// The script lives in the app because the input is a PDF, which has nowhere to
// put it. Both authors write to the same copy: the author types here, and
// Claude Code writes through the narration API — which is why the shell keeps
// polling, and why an incoming poll must never overwrite what is being typed.
export default function NarrationView({ project }) {
  const toast = useToast()

  const [slides, setSlides] = useState(project.slides || [])
  const [current, setCurrent] = useState(0)
  const [saveState, setSaveState] = useState('idle')

  const timers = useRef({})
  const pending = useRef({})
  const activeThumbRef = useRef(null)

  const review = project.review?.total ? project.review : null

  // Take the shell's poll, but keep any locally-unsaved edit on top of it.
  useEffect(() => {
    setSlides(
      (project.slides || []).map((s) =>
        pending.current[s.index] !== undefined
          ? { ...s, narration: pending.current[s.index] }
          : s
      )
    )
  }, [project.slides])

  // A deck that shrank on re-upload can leave the selection past the end.
  useEffect(() => {
    if (current > slides.length - 1) setCurrent(Math.max(0, slides.length - 1))
  }, [slides.length, current])

  // Keep the selected thumbnail visible. `block: 'nearest'` so this never
  // scrolls the page itself, only the strip.
  useEffect(() => {
    activeThumbRef.current?.scrollIntoView({
      behavior: 'smooth',
      block: 'nearest',
      inline: 'center',
    })
  }, [current])

  // On unmount — switching screens, not just closing the tab — cancel the
  // pending autosave timers but fire their saves first, so leaving the screen
  // mid-edit never drops a keystroke. Calls the API directly rather than
  // flush(), which would setState on an unmounted component.
  useEffect(() => {
    const pendingRef = pending.current
    const timersRef = timers.current
    return () => {
      Object.values(timersRef).forEach(clearTimeout)
      Object.entries(pendingRef).forEach(([index, text]) => {
        api.saveNarration(project.id, Number(index), text).catch(() => {})
      })
    }
  }, [project.id])

  const flush = useCallback(
    async (index) => {
      const text = pending.current[index]
      if (text === undefined) return
      delete pending.current[index]
      setSaveState('saving')
      try {
        await api.saveNarration(project.id, index, text)
        setSaveState((s) => (s === 'saving' ? 'saved' : s))
      } catch (err) {
        setSaveState('error')
        toast.error(`Autosave failed: ${err.message}`)
      }
    },
    [project.id, toast]
  )

  const flushNow = useCallback(
    (index) => {
      clearTimeout(timers.current[index])
      return flush(index)
    },
    [flush]
  )

  // Waving a slide through: its narration still fits the changed slide, so drop
  // the flag without touching the text (and without re-synthesizing its audio).
  const keepAsIs = useCallback(
    async (index) => {
      try {
        await api.clearReview(project.id, [index])
        setSlides((prev) =>
          prev.map((s) => (s.index === index ? { ...s, change: null } : s))
        )
      } catch (err) {
        toast.error(err.message)
      }
    },
    [project.id, toast]
  )

  const clearAll = useCallback(async () => {
    try {
      await api.clearReview(project.id)
      setSlides((prev) => prev.map((s) => ({ ...s, change: null })))
    } catch (err) {
      toast.error(err.message)
    }
  }, [project.id, toast])

  const onEdit = (index, text) => {
    setSlides((prev) =>
      // Editing a flagged slide is exactly what the flag was asking for; the
      // backend drops it on save, so drop it here too rather than let the poll
      // blink it away a few seconds later.
      prev.map((s) =>
        s.index === index ? { ...s, narration: text, change: null } : s
      )
    )
    pending.current[index] = text
    setSaveState('dirty')
    clearTimeout(timers.current[index])
    timers.current[index] = setTimeout(() => flush(index), AUTOSAVE_MS)
  }

  const go = async (i) => {
    const s = slides[current]
    if (s) await flushNow(s.index)
    setCurrent(Math.max(0, Math.min(slides.length - 1, i)))
  }

  if (!slides.length) return null

  const slide = slides[Math.min(current, slides.length - 1)]
  const { words, seconds } = estimateSeconds(slide?.narration)
  const slideChange = CHANGE_LABELS[slide?.change]
  const flagged = slides.filter((s) => s.change)
  const totals = slides.reduce(
    (acc, s) => {
      const est = estimateSeconds(s.narration)
      acc.seconds += est.seconds
      if (!s.narration?.trim()) acc.empty += 1
      return acc
    },
    { seconds: 0, empty: 0 }
  )

  return (
    <div className="animate-fadein space-y-3">
      <DraftStatus slides={slides} />

      {review && (
        <ReviewSummary review={review}>
          <div className="flex flex-shrink-0 gap-2">
            {flagged.length > 0 && (
              <Button
                variant="subtle"
                size="sm"
                onClick={() => go(slides.indexOf(flagged[0]))}
              >
                Go to first flagged
              </Button>
            )}
            <Button variant="ghost" size="sm" onClick={clearAll}>
              Dismiss
            </Button>
          </div>
        </ReviewSummary>
      )}

      {/* Thumbnail strip. Horizontal scroll keeps it one row however long the
          deck is; the active thumb is scrolled into view when you page. */}
      <div className="scroll-thin flex gap-2 overflow-x-auto rounded-xl border border-slate-200/60 bg-white p-2 shadow-sm">
        {slides.map((s, i) => {
          const est = estimateSeconds(s.narration)
          const empty = !s.narration?.trim()
          const active = i === current
          const change = CHANGE_LABELS[s.change]
          return (
            <button
              key={s.index}
              ref={active ? activeThumbRef : null}
              onClick={() => go(i)}
              title={`${i + 1}. ${s.title || `Slide ${i + 1}`} — ${
                empty ? 'no narration' : `~${est.seconds}s`
              }${change ? ` · ${change.label} in the new PDF` : ''}`}
              className={`group relative aspect-video w-[104px] flex-shrink-0 overflow-hidden rounded-lg border-2 transition ${
                active
                  ? 'border-brand-600 ring-2 ring-brand-500/20'
                  : 'border-line hover:border-slate-300'
              }`}
            >
              {s.image_url ? (
                <img
                  src={toRel(s.image_url)}
                  alt=""
                  loading="lazy"
                  className="h-full w-full object-cover"
                />
              ) : (
                <span className="flex h-full w-full items-center justify-center bg-slate-50 text-xs text-muted">
                  {i + 1}
                </span>
              )}
              <span
                className={`absolute bottom-0 left-0 rounded-tr-md px-1.5 py-0.5 text-[0.65rem] font-bold tabular-nums ${
                  active ? 'bg-brand-600 text-white' : 'bg-white/85 text-slate'
                }`}
              >
                {i + 1}
              </span>
              {empty && (
                <span
                  className="absolute right-1 top-1 h-2 w-2 rounded-full bg-amber-500 ring-1 ring-white"
                  aria-label="No narration"
                />
              )}
              {change && (
                <span
                  className={`absolute left-0 top-0 rounded-br-md px-1.5 py-0.5 text-[0.6rem] font-bold uppercase tracking-wide text-white ${change.dot}`}
                >
                  {change.label}
                </span>
              )}
            </button>
          )
        })}
      </div>

      {/* Slide · editor, side by side under the strip */}
      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="flex h-[58vh] flex-col rounded-xl border border-slate-200/60 bg-white p-3 shadow-sm">
          <div className="flex flex-1 items-center justify-center overflow-hidden rounded-lg bg-slate-50">
            {slide?.image_url ? (
              <img
                src={toRel(slide.image_url)}
                alt={`Slide ${current + 1}`}
                className="max-h-full max-w-full object-contain"
              />
            ) : (
              <div className="text-muted">Slide {current + 1}</div>
            )}
          </div>
          <div className="mt-2 flex items-center justify-between px-1 text-xs text-muted">
            <span>
              Slide {current + 1} of {slides.length}
            </span>
            <span className="truncate pl-2 font-medium text-slate">
              {slide?.title}
            </span>
          </div>
        </div>

        <div className="flex h-[58vh] flex-col">
          <div className="mb-1.5 flex items-baseline justify-between">
            <span className="text-sm font-semibold text-navy">Narration</span>
            <span className="flex items-baseline gap-3">
              <SaveIndicator state={saveState} />
              <span className="text-xs text-muted tabular-nums">
                {words} words · ~{seconds} sec
              </span>
            </span>
          </div>
          {slideChange && (
            <div className="mb-1.5 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-brand-200 bg-brand-50/60 px-3 py-2 text-xs">
              <span className="text-slate">
                {slide.change === 'new'
                  ? 'This slide is new in the PDF you uploaded — it has no narration yet.'
                  : 'This slide changed in the PDF you uploaded. The script below is the one it had before.'}
              </span>
              <Button
                variant="subtle"
                size="sm"
                onClick={() => keepAsIs(slide.index)}
              >
                <Check className="h-3.5 w-3.5" /> Keep as is
              </Button>
            </div>
          )}
          <textarea
            value={slide?.narration || ''}
            onChange={(e) => onEdit(slide.index, e.target.value)}
            onBlur={() => flushNow(slide.index)}
            placeholder="Empty — write the narration here, or ask Claude to draft it."
            className="scroll-thin w-full flex-1 resize-none rounded-xl border border-line bg-white p-4 text-sm leading-relaxed text-slate focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
          />
          <div className="mt-3 flex items-center justify-between">
            <Button
              variant="subtle"
              size="sm"
              disabled={current === 0}
              onClick={() => go(current - 1)}
            >
              <ArrowLeft className="h-4 w-4" /> Previous
            </Button>
            <span className="text-xs text-muted">
              {slides.length - totals.empty} of {slides.length} narrated ·
              ~{formatDuration(totals.seconds)} total
            </span>
            <Button
              variant="subtle"
              size="sm"
              disabled={current === slides.length - 1}
              onClick={() => go(current + 1)}
            >
              Next <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

function SaveIndicator({ state }) {
  const map = {
    idle: ['text-muted', ''],
    dirty: ['text-muted', 'Unsaved changes…'],
    saving: ['text-brand-dark', 'Saving…'],
    saved: ['text-green-600', 'All changes saved'],
    error: ['text-red-600', 'Save failed'],
  }
  const [cls, label] = map[state] || map.idle
  if (!label) return null
  return (
    <span className={`flex items-center gap-1.5 text-xs font-medium ${cls}`}>
      {state === 'saving' && <Spinner className="h-3 w-3" />}
      {state === 'saved' && <Check className="h-3.5 w-3.5" strokeWidth={3} />}
      {label}
    </span>
  )
}
