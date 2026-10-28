// Small API client. All paths are RELATIVE (no leading slash) so the SPA works
// behind a proxy / sub-path when served by FastAPI.

async function request(path, { method = 'GET', body, headers, raw } = {}) {
  const opts = { method, credentials: 'same-origin', headers: { ...headers } }
  if (body instanceof FormData) {
    opts.body = body
  } else if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json'
    opts.body = JSON.stringify(body)
  }
  const res = await fetch(path, opts)
  if (!res.ok) {
    let detail = res.statusText
    try {
      const data = await res.json()
      detail = data.detail || data.message || detail
    } catch {
      /* non-JSON error body */
    }
    const err = new Error(detail || `Request failed (${res.status})`)
    err.status = res.status
    throw err
  }
  if (raw) return res
  if (res.status === 204) return null
  const ct = res.headers.get('content-type') || ''
  return ct.includes('application/json') ? res.json() : res.text()
}

export const api = {
  // ---- decks ----
  listProjects: () => request('api/projects'),
  getProject: (id) => request(`api/projects/${id}`),
  // Start a new deck from a PDF chosen in the browser — the Upload screen with
  // no deck open, which is where a bare launch begins.
  createDeck: (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return request('api/projects/upload', { method: 'POST', body: fd })
  },
  // Upload an edited PDF into an existing deck: same deck, same settings, script
  // carried across slide by slide by content (see the backend's jobs._carry_over).
  uploadPdf: (id, file) => {
    const fd = new FormData()
    fd.append('file', file)
    return request(`api/projects/${id}/pdf`, { method: 'POST', body: fd })
  },
  // Re-read the PDF from the path the deck was opened with — for a deck the
  // author re-exported in place.
  reload: (id) => request(`api/projects/${id}/reload`, { method: 'POST' }),
  saveConfig: (id, config) =>
    request(`api/projects/${id}/config`, { method: 'PUT', body: config }),

  // ---- jobs ----
  build: (id) => request(`api/projects/${id}/build`, { method: 'POST' }),
  // Stop a running build. Clips already spoken stay cached for the next run.
  cancelBuild: (id) =>
    request(`api/projects/${id}/build/cancel`, { method: 'POST' }),

  // ---- narration ----
  // The script lives in the app. Claude writes it in bulk; the author edits
  // any slide by hand, autosaved a slide at a time.
  getNarration: (id) => request(`api/projects/${id}/narration`),
  saveNarration: (id, index, narration) =>
    request(`api/projects/${id}/narration/${index}`, {
      method: 'PUT',
      body: { narration },
    }),
  // Mark re-upload-flagged slides reviewed without editing them. Omit `indexes`
  // to clear every flag.
  clearReview: (id, indexes) =>
    request(`api/projects/${id}/review/clear`, {
      method: 'POST',
      body: { indexes: indexes ?? null },
    }),

  // ---- ElevenLabs voices (account + cloned) for the voice picker ----
  listVoices: () => request('api/tts/voices'),
  // Resolve a pasted Voice Library id to its name, labels and preview clip.
  // Works for any voice in the library, not only the account's own.
  getVoice: (voiceId) => request(`api/tts/voices/${encodeURIComponent(voiceId)}`),

  // ---- ElevenLabs API key (paste-in-app; validated + persisted server-side) ----
  ttsStatus: () => request('api/tts/status'),
  setTtsKey: (api_key) =>
    request('api/tts/key', { method: 'POST', body: { api_key } }),
  // How many TTS requests run at once. Account-wide (it follows the ElevenLabs
  // plan, not the deck), so it is not part of a deck's config.
  setTtsConcurrency: (concurrency) =>
    request('api/tts/concurrency', { method: 'POST', body: { concurrency } }),
}

// URL helpers (also relative)
export const videoUrl = (id) => `api/projects/${id}/video`
export const eventsUrl = (id) => `api/projects/${id}/events`

// Normalize a server-provided URL to a relative path (drop a leading slash) so
// it resolves correctly behind a sub-path.
export const toRel = (url) => (url ? url.replace(/^\//, '') : url)
