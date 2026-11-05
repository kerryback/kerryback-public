// Speech in the browser, off the page's main thread. One worker per role:
//   new Worker('/static/speech-worker.js?role=tts', {type: 'module'})  Kokoro 82M (open weights)
//   new Worker('/static/speech-worker.js?role=asr', {type: 'module'})  Whisper base.en
// Messages in:  {id, kind: 'load', voice, speed}   {id, kind: 'tts', text}   {id, kind: 'asr', samples}
// Messages out: {id, ok: true, ...result} or {id, ok: false, error}, and
//               {kind: 'progress', role, loaded, total} while the model downloads.
// The models download from Hugging Face the first time (Kokoro about 90 MB,
// Whisper about 80 MB) and the browser keeps them in its cache after that.

const role = new URL(self.location.href).searchParams.get('role');
const KOKORO = 'https://cdn.jsdelivr.net/npm/kokoro-js@1.2.1/dist/kokoro.web.js';
const TRANSFORMERS = 'https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.5.1/dist/transformers.web.min.js';
const KOKORO_MODEL = 'onnx-community/Kokoro-82M-v1.0-ONNX';
const WHISPER_MODEL = 'onnx-community/whisper-base.en';

let model = null, voice = 'af_heart', speed = 0.9;

function progress(p) {
  if (p && p.status === 'progress') self.postMessage({ kind: 'progress', role, file: p.file, loaded: p.loaded, total: p.total });
}

async function load(msg) {
  if (model) return {};
  voice = msg.voice || voice; speed = msg.speed || speed;
  if (role === 'tts') {
    const { KokoroTTS } = await import(KOKORO);
    model = await KokoroTTS.from_pretrained(KOKORO_MODEL, { dtype: 'q8', device: 'wasm', progress_callback: progress });
  } else {
    const { pipeline } = await import(TRANSFORMERS);
    model = await pipeline('automatic-speech-recognition', WHISPER_MODEL,
      { dtype: 'q8', device: 'wasm', progress_callback: progress });
  }
  return {};
}

// Whisper writes these for silence and noise; they are not speech.
const NOT_SPEECH = /^\s*(\[[^\]]*\]|\([^)]*\)|thank you\.?|you)\s*$/i;

self.onmessage = async ({ data: msg }) => {
  try {
    if (msg.kind === 'load') { self.postMessage({ id: msg.id, ok: true, ...(await load(msg)) }); return; }
    if (!model) await load(msg);
    if (msg.kind === 'tts') {
      const out = await model.generate(msg.text, { voice, speed });
      const audio = out.audio;
      self.postMessage({ id: msg.id, ok: true, audio, rate: out.sampling_rate }, [audio.buffer]);
    } else if (msg.kind === 'asr') {
      const out = await model(msg.samples);
      const text = (out.text || '').trim();
      self.postMessage({ id: msg.id, ok: true, text: NOT_SPEECH.test(text) ? '' : text });
    }
  } catch (e) {
    self.postMessage({ id: msg.id, ok: false, error: String(e && e.message || e) });
  }
};
