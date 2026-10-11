import { useEffect, useRef, useState } from 'react'
import { PenLine } from 'lucide-react'
import { countNarrated } from '../constants'
import { ProgressBar, Spinner } from './ui'

// How long after the last slide landed we still describe Claude as writing. The
// skill writes a few slides at a time and the shell polls every 4s, so a gap
// shorter than this means a batch is being composed, not that nothing is coming.
const ARRIVING_MS = 30000

// How often to re-check that gap, so "writing" decays into "nothing arriving"
// on its own rather than waiting for the next poll to change something.
const TICK_MS = 5000

// What is happening to the narration right now, above the editor.
//
// The app cannot ask Claude Code anything — it only sees slides appear through
// the narration API — so this infers from arrivals rather than claiming to know:
// slides landing means writing is under way, and a quiet deck with empty slides
// says plainly that the author may have to go ask for it. Without this the
// wait after an upload looks identical to nothing happening at all, which is how
// a deck gets Generated while it is still silent.
export default function DraftStatus({ slides }) {
  const { total, narrated, empty } = countNarrated(slides)

  // `at: 0` on the first observation, so opening a half-written deck later does
  // not read as a fresh arrival.
  const seen = useRef(null)
  const [, setTick] = useState(0)

  useEffect(() => {
    if (seen.current === null) seen.current = { narrated, at: 0 }
    else if (narrated !== seen.current.narrated)
      seen.current = { narrated, at: Date.now() }
  }, [narrated])

  useEffect(() => {
    if (!empty) return undefined
    const iv = setInterval(() => setTick((t) => t + 1), TICK_MS)
    return () => clearInterval(iv)
  }, [empty])

  if (!total || !empty) return null

  const arriving = Date.now() - (seen.current?.at || 0) < ARRIVING_MS

  if (arriving) {
    return (
      <div className="space-y-2 rounded-xl border border-brand-200 bg-brand-50/60 px-4 py-3">
        <div className="flex items-center gap-2 text-sm">
          <Spinner className="h-4 w-4 text-brand-700" />
          <span className="font-semibold text-navy">
            Claude Code is writing the narration
          </span>
        </div>
        <ProgressBar
          progress={{
            message: 'Slides written so far',
            done: narrated,
            total,
          }}
        />
        <p className="text-xs text-muted">
          It writes a few slides at a time, so the thumbnails fill in as it goes.
          Anything already here can be edited now — your changes are not
          overwritten by what arrives next.
        </p>
      </div>
    )
  }

  return (
    <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm">
      <PenLine
        className="mt-0.5 h-4 w-4 flex-shrink-0 text-amber-700"
        aria-hidden="true"
      />
      <div className="min-w-0">
        <p className="font-semibold text-navy">
          {empty === total
            ? `No narration yet — ${total} slide${total === 1 ? '' : 's'}`
            : `${empty} of ${total} slides have no narration yet`}
        </p>
        <p className="mt-0.5 text-muted">
          Claude Code writes this for you, usually within a minute or two of the
          upload. If it has not appeared, go back to your Claude Code window and
          ask it to draft the narration — or write these slides yourself below.
        </p>
      </div>
    </div>
  )
}
