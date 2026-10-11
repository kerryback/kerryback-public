import { useEffect, useRef, useState } from 'react'
import { FileText, FileUp, RotateCw } from 'lucide-react'
import { api } from '../api'
import { JOB_TERMINALS } from '../constants'
import { useJobEvents } from '../hooks/useJobEvents'
import { useToast } from './Toast'
import { Button, Card, ErrorBanner, ProgressBar, Spinner, StatePill } from './ui'

// Upload: where a deck comes in. Two modes, one component —
//   no deck open   → the PDF starts a new deck (a bare launch lands here)
//   a deck open    → the PDF replaces this deck's slides
//
// Replacing is deliberately not starting over. The new pages are matched against
// the old ones by content, so a page that didn't change keeps its narration and
// its already-spoken audio, and only what actually moved comes back flagged.
export default function UploadView({ project, refresh, onDone, onOpen }) {
  const { progress, running, start } = useJobEvents()
  const toast = useToast()
  const [error, setError] = useState('')
  const [dragging, setDragging] = useState(false)
  const [busy, setBusy] = useState(false)
  const [decks, setDecks] = useState(null)
  const fileRef = useRef(null)

  const files = project?.files || {}

  // With no deck open, offer the ones this folder already knows about.
  useEffect(() => {
    if (project) return
    api
      .listProjects()
      .then(setDecks)
      .catch(() => setDecks([]))
  }, [project])

  const watch = (pid) =>
    start(pid, {
      terminals: JOB_TERMINALS.load,
      onDone: async () => {
        const p = await refresh()
        const r = p?.review
        toast.success(
          r?.total
            ? `Read ${p.slides.length} slides. Review the flagged ones.`
            : `Read ${p?.slides?.length || 0} slides.`
        )
        onDone?.()
      },
      onError: async (err, evt) => {
        setError(evt?.message || err.message)
        toast.error("Couldn't read that PDF.")
        await refresh()
      },
    })

  const upload = async (file) => {
    if (!file) return
    setError('')
    if (!/\.pdf$/i.test(file.name)) {
      setError(`${file.name} isn't a PDF. Export your slides to PDF first.`)
      return
    }
    setBusy(true)
    try {
      if (project) {
        await api.uploadPdf(project.id, file)
        await refresh()
        watch(project.id)
      } else {
        const created = await api.createDeck(file)
        onOpen?.(created.id)
        watch(created.id)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const rereadFromDisk = async () => {
    setError('')
    try {
      await api.reload(project.id)
      await refresh()
      watch(project.id)
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="animate-fadein space-y-3">
      <ErrorBanner message={error} />

      {running && (
        <Card className="p-4">
          <ProgressBar progress={progress} />
        </Card>
      )}

      {/* The author re-exported the PDF in place — offer the file they
          already have rather than making them find it in a picker. */}
      {project && files.changed && !files.missing && (
        <Card className="flex flex-wrap items-center justify-between gap-3 p-4">
          <span className="text-sm text-slate">
            <span className="font-semibold text-navy">{files.pdf}</span> has
            changed on disk since the app read it.
          </span>
          <Button variant="ghost" onClick={rereadFromDisk} disabled={running}>
            <RotateCw className="h-4 w-4" /> Read it again
          </Button>
        </Card>
      )}

      <Card className="p-6">
        <h2 className="text-base font-extrabold tracking-tight text-navy">
          {project ? 'Upload the PDF again' : 'Upload a PDF'}
        </h2>
        <p className="mt-1.5 max-w-2xl text-sm text-muted">
          {project ? (
            <>
              Changed your slides? Export them to PDF again and drop it here.
              Nothing you have written is thrown away: each new page is matched
              against the old deck by content, so a page that didn&apos;t change
              keeps its narration <em>and</em> the audio already spoken for it.
              Only pages that changed — or are new — come back flagged for
              another look.
            </>
          ) : (
            <>
              A deck is one file: the PDF you exported from your slides. Drop it
              here and the app reads a page image per slide; the narration is
              written here in the app, so there is nothing to keep in sync.
            </>
          )}
        </p>

        <div
          onDragOver={(e) => {
            e.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragging(false)
            upload(e.dataTransfer.files?.[0])
          }}
          onClick={() => fileRef.current?.click()}
          className={`mt-5 flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-6 py-12 text-center transition ${
            dragging
              ? 'border-brand-600 bg-brand-50/60'
              : 'border-slate-300 bg-slate-50 hover:border-brand-400 hover:bg-brand-50/30'
          }`}
        >
          {busy ? (
            <Spinner className="h-6 w-6 text-brand-600" />
          ) : (
            <FileUp className="h-7 w-7 text-brand-600" aria-hidden="true" />
          )}
          <span className="text-sm font-semibold text-navy">
            Drop the PDF here, or click to choose it
          </span>
          <span className="text-xs text-muted">
            PDF only — it is what every slide tool exports faithfully
          </span>
        </div>
        <input
          ref={fileRef}
          type="file"
          accept="application/pdf,.pdf"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0]
            e.target.value = '' // let the same filename be picked again
            upload(file)
          }}
        />

        {project && (
          <p className="mt-5 border-t border-line pt-4 text-xs text-muted">
            Currently narrating{' '}
            <span className="font-semibold text-slate">
              {files.pdf || 'this deck'}
            </span>
            {files.source_dir ? ` from ${files.source_dir}` : ''} ·{' '}
            {project.slides?.length || 0} slides
            {files.missing && ' · that file is no longer where the app found it'}
          </p>
        )}
      </Card>

      {/* Decks this folder has seen before, so a bare launch isn't a dead end. */}
      {!project && decks !== null && decks.length > 0 && (
        <Card className="divide-y divide-line">
          <p className="px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-muted">
            Or reopen a deck
          </p>
          {decks.map((d) => (
            <button
              key={d.id}
              onClick={() => onOpen?.(d.id)}
              className="flex w-full items-center gap-3 px-4 py-3 text-left transition hover:bg-slate-50"
            >
              <FileText className="h-4 w-4 flex-shrink-0 text-muted" />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-semibold text-navy">
                  {d.name}
                </span>
                <span className="block truncate text-xs text-muted">
                  {d.files?.pdf}
                </span>
              </span>
              <StatePill state={d.state} stale={d.stale} />
            </button>
          ))}
        </Card>
      )}
    </div>
  )
}
