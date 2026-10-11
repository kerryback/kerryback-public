import { useState } from 'react'
import { AlertTriangle, CheckCircle2, Film, RotateCw } from 'lucide-react'
import { videoUrl } from '../api'
import { Button, Card, Spinner } from './ui'

// Preview: the finished video. The MP4 and transcript are already on disk in the
// author's folder — this player is a convenience, not the deliverable, so
// there is no download button.
export default function PreviewView({ project, onGenerate, generating }) {
  const [nonce, setNonce] = useState(0)
  const built = project.state === 'built'
  // A build already in flight must not be offered a Generate button: the old
  // screen showed "No video yet — Generate now" on top of a running job, which
  // reads as though the click never landed. `generating` comes from the event
  // stream; project.state covers a reload that reattaches after the stream.
  const building = generating || project.state === 'building'

  if (building) {
    return (
      <Card className="animate-fadein p-10 text-center">
        <Spinner className="mx-auto h-8 w-8 text-brand-blue" />
        <h2 className="mt-3 text-base font-extrabold tracking-tight text-navy">
          Generating your video
        </h2>
        <p className="mx-auto mt-1.5 max-w-md text-sm text-muted">
          The narration is being spoken and the slides rendered. Progress is at
          the top of the screen. The player appears here the moment it is done,
          and the .mp4 and .txt are saved to your folder.
        </p>
      </Card>
    )
  }

  if (!built) {
    return (
      <Card className="animate-fadein p-10 text-center">
        <Film className="mx-auto h-8 w-8 text-muted" aria-hidden="true" />
        <h2 className="mt-3 text-base font-extrabold tracking-tight text-navy">
          No video yet
        </h2>
        <p className="mx-auto mt-1.5 max-w-md text-sm text-muted">
          Write the narration, pick a voice in Audio settings, then press
          Generate. The video appears here, and the .mp4 and .txt are saved to
          your folder.
        </p>
        <div className="mt-5">
          <Button onClick={onGenerate}>Generate now</Button>
        </div>
      </Card>
    )
  }

  return (
    <div className="animate-fadein space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {project.stale ? (
          <span className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm text-amber-700">
            <AlertTriangle className="h-4 w-4 flex-shrink-0" aria-hidden="true" />
            This video is from an earlier run — the narration or the audio
            settings have changed since. Generate again to update it; only the
            slides whose narration changed are spoken again.
          </span>
        ) : (
          <span className="flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-4 py-2.5 text-sm text-green-700">
            <CheckCircle2 className="h-4 w-4 flex-shrink-0" aria-hidden="true" />
            Saved <code className="mx-1">{project.id}.mp4</code> and
            <code className="mx-1">{project.id}.txt</code> to your folder.
          </span>
        )}
        <Button variant="subtle" onClick={() => setNonce((n) => n + 1)}>
          <RotateCw className="h-4 w-4" /> Reload player
        </Button>
      </div>

      <Card className="overflow-hidden p-0">
        <video
          key={`${project.updated_at}-${nonce}`}
          src={`${videoUrl(project.id)}?v=${project.updated_at || 0}-${nonce}`}
          controls
          className="h-[70vh] w-full bg-black"
        />
      </Card>
    </div>
  )
}
