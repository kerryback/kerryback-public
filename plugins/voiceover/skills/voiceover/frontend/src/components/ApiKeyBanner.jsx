import { useState, useEffect } from 'react'
import { KeyRound } from 'lucide-react'
import { api } from '../api'
import { Button, inputClass } from './ui'
import { useToast } from './Toast'

// App-wide notice shown when no ElevenLabs API key is configured. The app still
// runs (convert, draft/edit narration), but audio and the video can't be
// generated until a key is added. Rather than making the author hand-edit
// a file, they paste the key here; the server validates it against
// ElevenLabs, persists it to .env, and loads it live (no restart). On success we
// reload so the voice picker and Generate step pick up the now-configured key.
export default function ApiKeyBanner() {
  const [configured, setConfigured] = useState(null) // null = unknown (loading)
  const [key, setKey] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const toast = useToast()

  useEffect(() => {
    let alive = true
    api
      .ttsStatus()
      .then((res) => alive && setConfigured(!!res.configured))
      .catch(() => alive && setConfigured(true)) // don't nag on a transient error
    return () => {
      alive = false
    }
  }, [])

  if (configured === null || configured) return null

  const save = async () => {
    setError('')
    if (!key.trim()) {
      setError('Paste your ElevenLabs API key first.')
      return
    }
    setSaving(true)
    try {
      await api.setTtsKey(key.trim())
      toast.success('API key saved — voice generation is enabled.')
      // Reload so the voice picker and Generate step re-read the configured key.
      window.location.reload()
    } catch (err) {
      setError(err.message || 'Could not save the key.')
      setSaving(false)
    }
  }

  return (
    <div className="border-b border-amber-200 bg-amber-50">
      <div className="mx-auto max-w-6xl px-5 py-4">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-amber-100 text-amber-700">
            <KeyRound className="h-4 w-4" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-amber-900">
              Audio can’t be generated yet — add your ElevenLabs API key
            </p>
            <p className="mt-1 text-xs leading-relaxed text-amber-800">
              You can still read the deck and write its narration. To
              generate the voice audio and build the video, this app needs an
              ElevenLabs key. Don’t have one? Create a free account at{' '}
              <a
                href="https://elevenlabs.io/app/settings/api-keys"
                target="_blank"
                rel="noreferrer"
                className="font-medium underline"
              >
                elevenlabs.io
              </a>
              , then open your profile menu (bottom left) → API Keys → Create API
              Key, and copy it. Paste it below — it’s stored on your machine in{' '}
              <code className="rounded bg-amber-100 px-1">~/.voiceover/.env</code>{' '}
              and never leaves it except to call ElevenLabs.
            </p>
            <p className="mt-1.5 text-xs leading-relaxed text-amber-800">
              The free tier’s monthly quota is measured in minutes of audio, so
              it is enough to try this out but not to voice a full deck — if
              generation fails partway with a quota error, that is why.
            </p>
            <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center">
              <input
                type="password"
                className={`${inputClass} sm:max-w-md`}
                value={key}
                onChange={(e) => setKey(e.target.value)}
                placeholder="Paste ElevenLabs API key (starts with sk_…)"
                autoComplete="off"
                onKeyDown={(e) => e.key === 'Enter' && save()}
              />
              <Button
                variant="amber"
                onClick={save}
                loading={saving}
                className="shrink-0"
              >
                Save key
              </Button>
            </div>
            {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
          </div>
        </div>
      </div>
    </div>
  )
}
