import { useEffect, useMemo, useRef, useState } from 'react'
import { Check, ChevronDown } from 'lucide-react'
import { api } from '../api'
import {
  DEFAULT_TTS,
  ELEVEN_MODELS,
  SPEED_RANGE,
  V3_STABILITY_LEVELS,
  modelInfo,
} from '../constants'
import { useToast } from './Toast'
import { Card, ErrorBanner, Field, Spinner, inputClass } from './ui'

const AUTOSAVE_MS = 500

// Audio settings: which voice, which model, and how it reads. Settings autosave
// the way the narration does — Generate lives in the top bar, so there is no
// "apply" step to forget, and a settings change makes the built video stale on
// its own (store.build_signature covers them).
export default function VoiceView({ project }) {
  const cfg = project.config || {}
  const toast = useToast()

  const [voiceId, setVoiceId] = useState(cfg.voice_id || DEFAULT_TTS.voice_id)
  const [model, setModel] = useState(cfg.model || DEFAULT_TTS.model)
  const [stability, setStability] = useState(
    cfg.stability ?? DEFAULT_TTS.stability
  )
  const [similarity, setSimilarity] = useState(
    cfg.similarity_boost ?? DEFAULT_TTS.similarity_boost
  )
  const [style, setStyle] = useState(cfg.style ?? DEFAULT_TTS.style)
  const [speakerBoost, setSpeakerBoost] = useState(
    cfg.use_speaker_boost ?? DEFAULT_TTS.use_speaker_boost
  )
  const [speed, setSpeed] = useState(cfg.speed ?? DEFAULT_TTS.speed)

  const [voices, setVoices] = useState([])
  const [voicesConfigured, setVoicesConfigured] = useState(true)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState('')

  // How many TTS requests run at once. This one is an account setting, not a
  // deck setting: it follows the ElevenLabs plan, and it changes only how fast
  // clips are requested, never how they sound — so it stays out of the deck
  // config, whose build_signature would otherwise re-synthesize everything.
  const [concurrency, setConcurrency] = useState(null)

  // A voice pasted from the ElevenLabs Voice Library, resolved to its name so
  // the author can see what they pasted. `library` holds the resolved voice
  // once it is accepted; it is offered in the dropdown alongside the account's.
  const [libraryId, setLibraryId] = useState('')
  const [library, setLibrary] = useState(null)
  const [lookingUp, setLookingUp] = useState(false)
  const [lookupError, setLookupError] = useState('')

  // Fetch the account's ElevenLabs voices (includes cloned voices).
  useEffect(() => {
    let alive = true
    api
      .listVoices()
      .then((res) => {
        if (!alive) return
        setVoicesConfigured(res.configured)
        setVoices(res.voices || [])
      })
      .catch(() => {
        if (alive) setVoicesConfigured(true) // don't block on a transient error
      })
    return () => {
      alive = false
    }
  }, [])

  // A voice saved on this deck that the account doesn't list is a library voice
  // chosen earlier. Resolve it so it reads as a name rather than a bare id.
  useEffect(() => {
    if (!voicesConfigured || voices.length === 0) return
    if (library?.voice_id === voiceId) return
    if (voices.some((v) => v.voice_id === voiceId)) return
    let alive = true
    api
      .getVoice(voiceId)
      .then((v) => alive && setLibrary(v))
      .catch(() => {
        /* leave it showing the raw id */
      })
    return () => {
      alive = false
    }
  }, [voicesConfigured, voices, voiceId, library])

  const settings = useMemo(
    () => ({
      voice_id: voiceId,
      model,
      stability: Number(stability),
      similarity_boost: Number(similarity),
      style: Number(style),
      use_speaker_boost: speakerBoost,
      speed: Number(speed),
    }),
    [voiceId, model, stability, similarity, style, speakerBoost, speed]
  )

  // Autosave. Debounced, because the sliders fire on every pixel.
  const first = useRef(true)
  useEffect(() => {
    if (first.current) {
      first.current = false
      return
    }
    setSaved(false)
    const t = setTimeout(() => {
      api
        .saveConfig(project.id, settings)
        .then(() => setSaved(true))
        .catch((err) => setError(err.message))
    }, AUTOSAVE_MS)
    return () => clearTimeout(t)
  }, [project.id, settings])

  const lookUpLibraryVoice = async () => {
    const id = libraryId.trim()
    if (!id) return
    setLookingUp(true)
    setLookupError('')
    try {
      const v = await api.getVoice(id)
      setLibrary(v)
      setVoiceId(v.voice_id)
      setLibraryId('')
      toast.success(`Voice set to ${v.name}.`)
    } catch (err) {
      setLookupError(err.message || 'Could not look up that voice.')
    } finally {
      setLookingUp(false)
    }
  }

  // Current concurrency, read once. Rendered only after it arrives so the
  // select never flashes a value the server disagrees with.
  useEffect(() => {
    let alive = true
    api
      .ttsStatus()
      .then((res) => alive && setConcurrency(res.concurrency ?? 2))
      .catch(() => alive && setConcurrency(2))
    return () => {
      alive = false
    }
  }, [])

  async function changeConcurrency(n) {
    const previous = concurrency
    setConcurrency(n)
    try {
      await api.setTtsConcurrency(n)
      toast.success(`Up to ${n} clip${n === 1 ? '' : 's'} at a time`)
    } catch (e) {
      setConcurrency(previous)
      setError(e.message || 'Could not save that.')
    }
  }

  const info = modelInfo(model)

  return (
    <div className="animate-fadein space-y-3">
      <ErrorBanner message={error} />

      <Card className="p-5">
        <div className="mb-4 flex items-baseline justify-between">
          <h2 className="text-base font-extrabold tracking-tight text-navy">
            Voice
          </h2>
          {saved && (
            <span className="flex items-center gap-1.5 text-xs font-medium text-green-600">
              <Check className="h-3.5 w-3.5" strokeWidth={3} /> Settings saved
            </span>
          )}
        </div>

        <div className="grid gap-5 lg:grid-cols-2">
          <Field
            label="Voice"
            hint="Your ElevenLabs account, cloned voices included"
          >
            {voicesConfigured ? (
              <div className="relative">
                <select
                  className={`${inputClass} appearance-none pr-9`}
                  value={voiceId}
                  onChange={(e) => setVoiceId(e.target.value)}
                >
                  {/* Keep the current value selectable even if it isn't in the
                      fetched list (not loaded yet, or a premade voice usable by
                      ID that the account's voice list doesn't return). Once it
                      resolves against the Voice Library it shows as a name. */}
                  {!voices.some((v) => v.voice_id === voiceId) &&
                    (library?.voice_id === voiceId ? (
                      <option value={voiceId}>
                        {library.name} (Voice Library)
                      </option>
                    ) : (
                      <option value={voiceId}>
                        {voices.length === 0 ? voiceId : `Current: ${voiceId}`}
                      </option>
                    ))}
                  {voices.map((v) => (
                    <option key={v.voice_id} value={v.voice_id}>
                      {v.name}
                      {v.category === 'cloned' ? ' (cloned)' : ''}
                    </option>
                  ))}
                </select>
                <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
              </div>
            ) : (
              <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
                Add your ElevenLabs API key in the banner at the top of the page
                to load your account&apos;s voices.
              </div>
            )}
          </Field>

          <Field label="Model" hint="Expressiveness vs. speed">
            <div className="relative">
              <select
                className={`${inputClass} appearance-none pr-9`}
                value={model}
                onChange={(e) => setModel(e.target.value)}
              >
                {ELEVEN_MODELS.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.label}
                  </option>
                ))}
              </select>
              <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
            </div>
          </Field>

          {/* The account lists ~20 premade voices plus your own clones. The rest
              of ElevenLabs' library — thousands of voices — is browsable only on
              their site, which is also where you can audition them. Paste the id
              of one here; text-to-speech takes a library voice directly, with no
              add-to-my-voices step. */}
          {voicesConfigured && (
            <Field label="Voice Library" hint="Paste an ID from elevenlabs.io">
              <div className="flex gap-2">
                <input
                  className={inputClass}
                  value={libraryId}
                  placeholder="e.g. 21m00Tcm4TlvDq8ikWAM"
                  onChange={(e) => {
                    setLibraryId(e.target.value)
                    setLookupError('')
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault()
                      lookUpLibraryVoice()
                    }
                  }}
                />
                <button
                  type="button"
                  onClick={lookUpLibraryVoice}
                  disabled={!libraryId.trim() || lookingUp}
                  className="inline-flex items-center gap-2 rounded-lg border border-line bg-white px-4 py-2 text-sm font-semibold text-slate transition hover:bg-slate-50 disabled:opacity-50"
                >
                  {lookingUp && <Spinner />} Use
                </button>
              </div>
              {lookupError ? (
                <p className="mt-1.5 text-xs text-red-600">{lookupError}</p>
              ) : library && library.voice_id === voiceId ? (
                <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
                  <span className="font-semibold text-navy">{library.name}</span>
                  {library.labels?.length > 0 && (
                    <span>{library.labels.join(' · ')}</span>
                  )}
                  {library.preview_url && (
                    <audio
                      controls
                      src={library.preview_url}
                      className="h-7 max-w-[13rem]"
                    />
                  )}
                </div>
              ) : (
                <p className="mt-1.5 text-xs text-muted">
                  Browse and audition at elevenlabs.io/app/voice-library, then
                  copy the voice&apos;s ID.
                </p>
              )}
            </Field>
          )}
        </div>
      </Card>

      <Card className="p-5">
        <h2 className="mb-4 text-base font-extrabold tracking-tight text-navy">
          How it reads
        </h2>
        <div className="grid gap-5 lg:grid-cols-2">
          {/* v3 defines three named stability levels; the v2 family takes a
              continuous dial. Showing a slider for v3 would imply precision the
              model does not have. */}
          {info.discreteStability ? (
            <Field label="Stability" hint="How much range the read is allowed">
              <div className="grid grid-cols-3 gap-2">
                {V3_STABILITY_LEVELS.map((lv) => {
                  const active = Number(stability) === lv.value
                  return (
                    <button
                      key={lv.label}
                      type="button"
                      title={lv.hint}
                      onClick={() => setStability(lv.value)}
                      className={`rounded-lg border px-2 py-2 text-xs font-semibold transition ${
                        active
                          ? 'border-brand-600 bg-brand-50 text-brand-700'
                          : 'border-slate-200 bg-white text-muted hover:border-slate-300'
                      }`}
                    >
                      {lv.label}
                    </button>
                  )
                })}
              </div>
              <p className="mt-1.5 text-xs text-muted">
                {V3_STABILITY_LEVELS.find((lv) => Number(stability) === lv.value)
                  ?.hint || 'Pick a level.'}
              </p>
            </Field>
          ) : (
            <Field
              label={`Stability — ${Number(stability).toFixed(2)}`}
              hint="Lower is more expressive, higher is more consistent"
            >
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={stability}
                onChange={(e) => setStability(e.target.value)}
                className="w-full accent-brand-600"
              />
            </Field>
          )}

          <Field
            label={`Style — ${Number(style).toFixed(2)}`}
            hint="Emotional emphasis; 0 is a plain read"
          >
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={style}
              onChange={(e) => setStyle(e.target.value)}
              className="w-full accent-brand-600"
            />
          </Field>

          <Field
            label={`Speed — ${Number(speed).toFixed(2)}×`}
            hint="Below 1 is slower, above 1 is faster"
          >
            <input
              type="range"
              min={SPEED_RANGE.min}
              max={SPEED_RANGE.max}
              step={SPEED_RANGE.step}
              value={speed}
              onChange={(e) => setSpeed(e.target.value)}
              className="w-full accent-brand-600"
            />
          </Field>

          {/* "Source voice" used to read as something the author supplied.
              It is the recordings the voice itself was built from — your own
              samples for a cloned voice, ElevenLabs' originals for a premade
              one — so the label now says that, and says when to leave it be. */}
          <Field
            label={`Similarity boost — ${Number(similarity).toFixed(2)}`}
            hint="Matters mainly for cloned voices"
          >
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={similarity}
              onChange={(e) => setSimilarity(e.target.value)}
              className="w-full accent-brand-600"
            />
            <p className="mt-1.5 text-xs text-muted">
              How closely to copy the recordings this voice was built from. Higher
              tracks them more faithfully, including any noise in them. The default
              is fine for the built-in voices — this is not the flatness dial.
            </p>
          </Field>

          <label className="flex cursor-pointer items-start gap-2.5">
            <input
              type="checkbox"
              checked={speakerBoost}
              onChange={(e) => setSpeakerBoost(e.target.checked)}
              className="mt-0.5 h-4 w-4 accent-brand-600"
            />
            <span>
              <span className="block text-sm font-semibold text-navy">
                Speaker boost
              </span>
              <span className="block text-xs text-muted">
                Strengthens resemblance to the voice. Slightly slower to generate.
              </span>
            </span>
          </label>
        </div>

        <p className="mt-5 border-t border-line pt-4 text-xs text-muted">
          Changing any of these re-synthesizes the whole deck on the next
          Generate — every clip is cached under the voice it was made with.
          Editing one slide&apos;s narration costs only that slide.
        </p>
      </Card>

      {/* Account-wide, not part of the deck. ElevenLabs caps concurrent
          requests per plan and returns 429 above the cap, which fails the whole
          build — and their API reports the plan tier but not its limit, so this
          cannot be detected for you. */}
      <Card className="p-5">
        <h2 className="mb-4 text-base font-extrabold tracking-tight text-navy">
          ElevenLabs plan
        </h2>

        <div className="max-w-md">
          <Field label="Clips at a time" hint="Match your plan's limit">
            <div className="relative">
              <select
                className={`${inputClass} appearance-none pr-9`}
                value={concurrency ?? 2}
                disabled={concurrency === null}
                onChange={(e) => changeConcurrency(Number(e.target.value))}
              >
                <option value={1}>1 — slowest, always safe</option>
                <option value={2}>2 — Free</option>
                <option value={3}>3 — Starter</option>
                <option value={5}>5 — Creator</option>
                <option value={10}>10 — Pro</option>
                <option value={15}>15 — Scale or Business</option>
              </select>
              <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
            </div>
          </Field>
        </div>

        <p className="mt-4 text-xs text-muted">
          Set too high, ElevenLabs rejects the extra requests and the build
          fails; set lower than your plan allows and it simply takes longer.
          Applies to every deck, changes nothing about how the audio sounds, and
          never invalidates clips already generated.
        </p>
      </Card>
    </div>
  )
}
