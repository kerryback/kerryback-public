import { useCallback, useEffect, useState } from 'react'
import {
  AlertTriangle,
  Film,
  Headphones,
  PenLine,
  RotateCw,
  Sliders,
  Square,
  Upload,
} from 'lucide-react'
import { api } from './api'
import { JOB_TERMINALS, countNarrated } from './constants'
import { useJobEvents } from './hooks/useJobEvents'
import { ToastProvider, useToast } from './components/Toast'
import {
  Button,
  Card,
  ErrorBanner,
  ProgressBar,
  SlideTicks,
  Spinner,
  StatePill,
} from './components/ui'
import ApiKeyBanner from './components/ApiKeyBanner'
import NarrationView from './components/NarrationView'
import PreviewView from './components/PreviewView'
import UploadView from './components/UploadView'
import VoiceView from './components/VoiceView'

// The launcher opens the app at /?project=<id> when it was given a deck. Launched
// bare, it opens at / and the deck arrives through the Upload screen.
const initialProject = () =>
  new URLSearchParams(window.location.search).get('project') || null

// How often to re-read the deck. This is how narration Claude writes through the
// API shows up while the author watches.
const POLL_MS = 4000

// The screens, in the order they sit in the top bar. Left to right is the order
// things happen in for a new deck — but they are places, not steps: nothing is
// gated, and a finished deck is edited by going straight to whichever one.
const SCREENS = [
  { key: 'upload', label: 'Upload', icon: Upload },
  { key: 'narration', label: 'Narration text', icon: PenLine },
  { key: 'voice', label: 'Audio settings', icon: Sliders },
  { key: 'preview', label: 'Preview', icon: Film, after: 'generate' },
]

function Shell() {
  const [projectId, setProjectId] = useState(initialProject)
  const [project, setProject] = useState(null)
  const [screen, setScreen] = useState('narration')
  const [error, setError] = useState('')
  // Whether Generate was stopped for want of narration — a flag, not a count.
  // Claude is usually still writing while this is on screen, so the numbers in
  // it are read live at render time rather than frozen at the click.
  const [blocked, setBlocked] = useState(false)
  const { progress, running, start } = useJobEvents()
  // Stop was pressed and the build is winding down: clips already sent to
  // ElevenLabs are allowed to finish, which can take a few seconds.
  const [stopping, setStopping] = useState(false)
  const toast = useToast()

  const refresh = useCallback(async () => {
    if (!projectId) return null
    try {
      const p = await api.getProject(projectId)
      setProject(p)
      setError('')
      return p
    } catch (err) {
      setError(err.message)
      return null
    }
  }, [projectId])

  useEffect(() => {
    refresh()
    const iv = setInterval(refresh, POLL_MS)
    return () => clearInterval(iv)
  }, [refresh])

  // A deck uploaded in the app becomes this session's deck, and the URL says so
  // — reloading the tab (or handing the link to Claude) reopens the same deck.
  const openDeck = useCallback((pid) => {
    setProjectId(pid)
    setProject(null)
    setScreen('narration')
    const url = new URL(window.location.href)
    url.searchParams.set('project', pid)
    window.history.replaceState({}, '', url)
  }, [])

  const runBuild = useCallback(async () => {
    if (!project) return
    try {
      const status = await api.ttsStatus()
      if (!status.configured) {
        toast.error(
          'Add your ElevenLabs API key first — the banner at the top of the page.'
        )
        return
      }
      setBlocked(null)
      setStopping(false)
      await api.build(project.id)
      setScreen('preview')
      start(project.id, {
        terminals: JOB_TERMINALS.build,
        onDone: async () => {
          toast.success('Voiceover generated.')
          await refresh()
        },
        onError: async (err, evt) => {
          setStopping(false)
          toast.error(evt?.message || err.message)
          await refresh()
        },
        onCancel: async (evt) => {
          setStopping(false)
          toast.success(evt?.message || 'Generation stopped.')
          await refresh()
        },
      })
    } catch (err) {
      toast.error(err.message)
    }
  }, [project, refresh, start, toast])

  const stopBuild = useCallback(async () => {
    if (!project) return
    setStopping(true)
    try {
      await api.cancelBuild(project.id)
    } catch (err) {
      setStopping(false)
      toast.error(err.message)
    }
  }, [project, toast])

  // Generating a deck whose slides have no script spends ElevenLabs quota on a
  // video of silence, and the only sign is a transcript full of "(silent)" after
  // the fact. The usual way in is pressing Generate in the minute or two before
  // Claude's draft lands, so stop and say what is missing rather than build it.
  const generate = useCallback(() => {
    if (!project) return
    if (countNarrated(project.slides).empty) {
      setBlocked(true)
      return
    }
    runBuild()
  }, [project, runBuild])

  // The last slide landing while the warning is up answers it; don't leave a
  // spent objection on screen for the author to work around.
  useEffect(() => {
    if (blocked && !countNarrated(project?.slides).empty) setBlocked(false)
  }, [blocked, project])

  // No deck yet: the top bar would have nothing to act on, so the Upload screen
  // is the whole app until a PDF arrives.
  if (!projectId) {
    return (
      <div className="min-h-full flex flex-col">
        <BareBar />
        <ApiKeyBanner />
        <main className="mx-auto w-full max-w-3xl flex-1 px-5 py-8">
          <UploadView refresh={async () => null} onOpen={openDeck} />
        </main>
      </div>
    )
  }

  const busy = running || project?.state === 'loading'
  // project.state covers a reload mid-build, when the event stream is gone but
  // the job is still running on the server.
  const generating = running || project?.state === 'building'
  const built = project?.state === 'built'

  return (
    <div className="min-h-full flex flex-col">
      <TopBar
        project={project}
        screen={screen}
        onScreen={setScreen}
        onGenerate={generate}
        onStop={stopBuild}
        generating={generating}
        stopping={stopping}
        busy={busy}
        built={built}
      />
      <ApiKeyBanner />
      <main className="mx-auto w-full max-w-[1600px] flex-1 px-5 py-5">
        <ErrorBanner message={error} onRetry={refresh} />

        {!project ? (
          <div className="flex items-center justify-center py-24 text-muted">
            <Spinner className="h-6 w-6 text-brand-blue" />
          </div>
        ) : (
          <div className="space-y-3">
            {running && (
              <Card className="space-y-3 p-4">
                <ProgressBar progress={progress} tone="amber" />
                <SlideTicks
                  total={progress?.total || project.slides?.length || 0}
                  done={progress?.done || 0}
                />
                <p className="text-xs text-muted">
                  Speaking the narration, then rendering the video — a couple of
                  minutes for a long deck. Only slides whose narration changed
                  since the last run are spoken again; the rest are reused.
                </p>
              </Card>
            )}

            {blocked && !running && (
              <NothingToSay
                counts={countNarrated(project.slides)}
                onAnyway={runBuild}
                onWrite={() => setScreen('narration')}
                onDismiss={() => setBlocked(false)}
              />
            )}

            {/* A failed build is usually the ElevenLabs quota, and the reason
                only ever appeared as a toast — gone by the time anyone reads
                the state pill. Keep it on screen until the next run. */}
            {project.state === 'building_failed' && !running && (
              <BuildFailed project={project} onRetry={generate} />
            )}

            {project.state === 'load_failed' ? (
              <LoadFailed
                project={project}
                onReupload={() => setScreen('upload')}
              />
            ) : project.state === 'loading' && !project.slides?.length ? (
              <div className="flex items-center justify-center gap-2 py-24 text-muted">
                <Spinner className="h-5 w-5 text-brand-blue" /> Reading the PDF…
              </div>
            ) : screen === 'upload' ? (
              <UploadView
                project={project}
                refresh={refresh}
                onOpen={openDeck}
                onDone={() => setScreen('narration')}
              />
            ) : screen === 'narration' ? (
              <NarrationView project={project} />
            ) : screen === 'voice' ? (
              <VoiceView project={project} />
            ) : (
              <PreviewView
                project={project}
                onGenerate={generate}
                generating={running}
              />
            )}
          </div>
        )}
      </main>
    </div>
  )
}

function Brand({ children }) {
  return (
    <div className="flex min-w-0 items-center gap-2.5">
      <span className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-white/10">
        <Headphones className="h-4 w-4" />
      </span>
      <div className="min-w-0">{children}</div>
    </div>
  )
}

function BareBar() {
  return (
    <header className="border-b border-navy/40 bg-navy text-white">
      <div className="mx-auto flex max-w-3xl items-center gap-3 px-5 py-2.5">
        <Brand>
          <span className="block text-sm font-extrabold leading-tight tracking-tight">
            Voiceover
          </span>
          <span className="block text-[0.7rem] text-white/60">
            Upload a PDF to begin
          </span>
        </Brand>
      </div>
    </header>
  )
}

function TopBar({
  project,
  screen,
  onScreen,
  onGenerate,
  onStop,
  generating,
  stopping,
  busy,
  built,
}) {
  const files = project?.files
  const changed = files?.changed && !files?.missing
  return (
    <header className="sticky top-0 z-30 border-b border-navy/40 bg-navy text-white">
      <div className="mx-auto flex max-w-[1600px] flex-wrap items-center justify-between gap-3 px-5 py-2.5">
        <Brand>
          <span className="block truncate text-sm font-extrabold leading-tight tracking-tight">
            {project?.name || 'Voiceover'}
          </span>
          {files?.pdf && (
            <span
              className="block truncate text-[0.7rem] text-white/60"
              title={files.source_dir || files.pdf}
            >
              {files.pdf}
            </span>
          )}
        </Brand>

        {/* Generate sits in the row with the screens, between Audio settings and
            Preview — where it falls in the order of doing things, and reachable
            from wherever you are. */}
        <nav className="flex flex-wrap items-center gap-1">
          {SCREENS.map((s) => {
            const active = screen === s.key
            const Icon = s.icon
            return (
              <span key={s.key} className="flex items-center gap-1">
                {/* While a run is going, Generate becomes Stop, in the same
                    place: that is where the eye goes on realizing a slide
                    still needs changing. */}
                {s.after === 'generate' && generating && (
                  <Button
                    variant="danger"
                    size="sm"
                    className="mx-1"
                    onClick={onStop}
                    loading={stopping}
                    title="Stop generating. Clips already spoken are kept, so the next run picks up where this one left off."
                  >
                    {stopping ? (
                      'Stopping…'
                    ) : (
                      <>
                        <Square className="h-3.5 w-3.5" /> Stop
                      </>
                    )}
                  </Button>
                )}
                {s.after === 'generate' && !generating && (
                  <Button
                    variant={built ? 'amber' : 'primary'}
                    size="sm"
                    className="mx-1"
                    onClick={onGenerate}
                    disabled={busy || !project?.slides?.length}
                    title="Speak the narration and render the video. Only slides whose narration changed are spoken again."
                  >
                    {built ? (
                      <>
                        <RotateCw className="h-3.5 w-3.5" /> Regenerate
                      </>
                    ) : (
                      <>
                        <Headphones className="h-3.5 w-3.5" /> Generate
                      </>
                    )}
                  </Button>
                )}
                <button
                  onClick={() => onScreen(s.key)}
                  aria-current={active ? 'page' : undefined}
                  className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                    active
                      ? 'bg-white text-navy'
                      : 'text-white/75 hover:bg-white/10 hover:text-white'
                  }`}
                >
                  <Icon className="h-3.5 w-3.5" /> {s.label}
                  {/* The one thing worth a dot up here: the PDF on disk moved on
                      without the app. */}
                  {s.key === 'upload' && changed && (
                    <span
                      className="h-1.5 w-1.5 rounded-full bg-accent-500"
                      aria-label="The PDF changed on disk"
                    />
                  )}
                </button>
              </span>
            )
          })}
        </nav>

        {project && <StatePill state={project.state} stale={project.stale} />}
      </div>
    </header>
  )
}

// Generate, stopped because slides have no script. Not a modal: the fix is on
// another screen, and a dialog would have to be dismissed before going there.
// "Generate anyway" stays available — a deliberately part-narrated deck is a
// legitimate thing to build, and this is a warning, not a rule.
function NothingToSay({ counts, onAnyway, onWrite, onDismiss }) {
  const { empty, total } = counts
  const all = empty === total
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm">
      <span className="flex min-w-0 items-start gap-2">
        <AlertTriangle
          className="mt-0.5 h-4 w-4 flex-shrink-0 text-amber-700"
          aria-hidden="true"
        />
        <span className="min-w-0">
          <span className="block font-semibold text-navy">
            {all
              ? 'Nothing to say yet — this deck has no narration'
              : `${empty} of ${total} slides have no narration`}
          </span>
          <span className="block text-muted">
            {all
              ? 'Generating now would render a silent video and spend nothing but time. Claude Code usually has the draft in within a minute or two of the upload.'
              : 'Those slides would be silent in the video, held on screen for four seconds each.'}
          </span>
        </span>
      </span>
      <span className="flex flex-shrink-0 gap-2">
        <Button variant="subtle" size="sm" onClick={onWrite}>
          <PenLine className="h-3.5 w-3.5" /> Narration text
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            onDismiss()
            onAnyway()
          }}
        >
          Generate anyway
        </Button>
      </span>
    </div>
  )
}

function BuildFailed({ project, onRetry }) {
  const message = (project.log || '').split('\n')[0]
  const quota = /quota|credit|402|429/i.test(message)
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
      <span className="flex min-w-0 items-start gap-2">
        <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0" aria-hidden="true" />
        <span className="min-w-0">
          <span className="block font-semibold">Generation failed</span>
          <span className="block whitespace-pre-wrap break-words text-red-600/90">
            {message || 'The video could not be generated.'}
          </span>
          {quota && (
            <span className="mt-1 block text-red-600/90">
              The slides already spoken are cached, so trying again after topping
              up re-synthesizes only what is left.
            </span>
          )}
        </span>
      </span>
      <Button variant="danger" size="sm" onClick={onRetry}>
        <RotateCw className="h-4 w-4" /> Try again
      </Button>
    </div>
  )
}

// A PDF that can't be read is nearly always a file that isn't really a PDF, or
// one that is encrypted. Say what happened and point at the one screen that can
// fix it.
function LoadFailed({ project, onReupload }) {
  const message = (project.log || '').split('\n')[0]
  return (
    <Card className="p-6">
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-600" />
        <div className="min-w-0 flex-1">
          <h2 className="text-base font-extrabold tracking-tight text-navy">
            Couldn&apos;t read this PDF
          </h2>
          <p className="mt-1.5 whitespace-pre-wrap text-sm text-slate">
            {message || 'The PDF could not be read.'}
          </p>
          <div className="mt-4">
            <Button onClick={onReupload}>
              <Upload className="h-4 w-4" /> Upload a PDF
            </Button>
          </div>
        </div>
      </div>
    </Card>
  )
}

export default function App() {
  return (
    <ToastProvider>
      <Shell />
    </ToastProvider>
  )
}
