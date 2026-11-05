// Voice version of the page: a whiteboard. The tutor's prose is spoken and
// never shown; headings, list items, tables, equations and trees are shown on
// the board and never spoken. Each "## Title" line in a reply starts a new
// section of the board, like a page; the student can page back through them.
//
// index.html imports this module only when /api/config reports voice: true,
// then calls init(). Importing it has no side effects, so the pure helpers
// below can be tested in node.
//
// Interface used by index.html, on window.voice:
//   addMsg(role, text)  show a whole message ('tutor' | 'student' | 'error')
//   addNode(el)         put an element (a tree) in the current section
//   tutorText(delta)    a streamed piece of the tutor's reply
//   tutorEnd()          the streamed reply (or the text before a tree) is complete
//   render(display)     rebuild the board from a saved conversation
//   begin(view, startChat)  the chat is on screen: wait for Start, then run
//   onChatEvent(ev), onTurnStart(), onTurnEnd()
//   stop()              the conversation is replaced (new session, sign out)
//   audioBusy           true while the tutor's audio is still playing
//
// Optional hooks, passed to init() beside isBusy and chat, replace the server's
// speech routes (the Claude Code plugin speaks and listens in the browser):
//   synth(text)         -> Promise of {audio: Float32Array, rate}; used instead of
//                          GET /api/say/<n>. Say events then carry their text.
//   transcribe(samples) -> Promise of the transcript of 16 kHz Float32 samples;
//                          used instead of POST /api/listen
//   isReady()           -> true once the voice can run; used instead of /api/config
//   notice              the line on the Start card, instead of NOTICE
//
// Listening: after Start, when the tutor has finished speaking and no turn is
// running, the microphone opens and Silero VAD (vad-web) waits for the student
// to speak. Each finished utterance goes to POST /api/listen as a WAV and the
// transcript is sent as the student's message. The app never listens while the
// tutor speaks or thinks. idle_seconds after listening starts (see
// idle-deadline.js: noise, misfires and empty transcripts do not postpone it;
// only a sent transcript does), or when one speech segment runs 60 s, the
// microphone closes, the tutor says the idle line, and Resume reopens it.
// Pause freezes the tutor mid-sentence and closes the microphone; Resume picks
// up where it stopped. A hidden tab releases the microphone.

import { createIdleDeadline } from './idle-deadline.js';
import { encodeWav } from './wav.js';

const KATEX = 'https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.11/';
const WHITEBOARD_FONT = 'https://fonts.googleapis.com/css2?family=Kalam:wght@400;700&display=swap';
const LOUDNESS_SCALE = 5;   // RMS 0.1 (normal speech) -> 0.5, RMS 0.2 -> 1
// vad-web 0.0.31 with onnxruntime-web 1.22.0, the pair in vad-web's own quick start.
const ORT_CDN = 'https://cdn.jsdelivr.net/npm/onnxruntime-web@1.22.0/dist/';
const VAD_CDN = 'https://cdn.jsdelivr.net/npm/@ricky0123/vad-web@0.0.31/dist/';
// The tutor's name and subtitle come from tutor.toml, on <body data-name data-subtitle>.
const page = () => (typeof document !== 'undefined' && document.body?.dataset) || {};
const NOTICE_KEY = () => `${page().name || 'tutor'}-voice-notice`;
const NOTICE = 'Your speech is sent to the course server to be turned into text. The recording is not kept.';
const VAD_RATE = 16000;     // vad-web gives 16 kHz samples
// User gestures that may resume the AudioContext. iOS Safari needs touchend or click.
export const UNLOCK_EVENTS = ['pointerdown', 'keydown', 'touchend', 'click'];

// --- pure helpers ------------------------------------------------------------

const token = (k) => `@@math${k}@@`;

// Pull $$...$$ blocks out before Markdown parsing. Each block becomes a
// placeholder paragraph. With partial (the reply is still streaming), an
// unclosed $$ and a trailing $ are cut off, so raw LaTeX never flashes.
export function splitMath(text, partial = false) {
  const blocks = [];
  let md = '', i = 0;
  for (;;) {
    const a = text.indexOf('$$', i);
    if (a < 0) { md += text.slice(i); if (partial && md.endsWith('$')) md = md.slice(0, -1); break; }
    const b = text.indexOf('$$', a + 2);
    if (b < 0) { md += partial ? text.slice(i, a) : text.slice(i); break; }
    md += text.slice(i, a) + `\n\n${token(blocks.length)}\n\n`;
    blocks.push(text.slice(a + 2, b).trim());
    i = b + 2;
  }
  return { md, blocks };
}

// Put the rendered blocks back into the sanitized HTML.
export function fillMath(html, blocks, renderTex) {
  return html.replace(/<p>@@math(\d+)@@<\/p>|@@math(\d+)@@/g, (_, a, b) =>
    `<div class="board math">${renderTex(blocks[+(a ?? b)] ?? '')}</div>`);
}

// A prose paragraph with "=" in it is a formula line ("Find: σ = ?"): mark it
// so the board shows it, although prose is otherwise only spoken.
export function markFormulaLines(html) {
  return html.replace(/<p>((?:(?!<\/p>)[\s\S])*?=(?:(?!<\/p>)[\s\S])*?)<\/p>/g, '<p class="formula">$1</p>');
}

export function stripBold(html) {
  return html.replace(/<\/?(strong|b)\b[^>]*>/g, '');
}

// Split a reply at "## Title" lines. Returns [{title, body}], where title is
// null for text before the first heading. While streaming (final false), a
// heading counts only once its line is complete.
export function splitSections(text, final = false) {
  const parts = [{ title: null, body: '' }];
  const re = /^##[ \t]+(.+?)[ \t]*$/gm;
  let i = 0, m;
  while ((m = re.exec(text))) {
    const end = m.index + m[0].length;
    if (!final && text[end] !== '\n') break;
    parts[parts.length - 1].body += text.slice(i, m.index);
    parts.push({ title: m[1].replace(/[*_`]/g, ''), body: '' });
    i = end + 1;
  }
  let rest = text.slice(i);
  if (!final) {   // a line that may still become a heading is held back until it is complete
    const nl = rest.lastIndexOf('\n');
    if (rest.slice(nl + 1).startsWith('#')) rest = rest.slice(0, nl + 1);
  }
  parts[parts.length - 1].body += rest;
  return parts.filter((p, k) => k > 0 || p.body.trim());
}

// The newest section the board may show: the last one whose gate (the clips
// queued before it was made) has been spoken. The first section is always due.
// -1 when there are no sections.
export function lastDueSection(gates, spoken) {
  let i = gates.length - 1;
  while (i > 0 && gates[i] > spoken) i--;
  return i;
}

// RMS of time-domain samples (-1..1), mapped to 0..1.
export function rmsLoudness(samples) {
  let sum = 0;
  for (const x of samples) sum += x * x;
  const rms = samples.length ? Math.sqrt(sum / samples.length) : 0;
  const v = Math.min(1, rms * LOUDNESS_SCALE);
  return Number.isFinite(v) ? v : 0;
}

// --- page --------------------------------------------------------------------

function escapeHtml(s) {
  const d = document.createElement('div'); d.textContent = s; return d.innerHTML;
}

function renderTex(tex) {
  if (window.katex) return window.katex.renderToString(tex, { displayMode: true, throwOnError: false });
  return `<code>${escapeHtml(tex)}</code>`;   // KaTeX failed to load: show the source
}

function loadKatex() {
  const css = document.createElement('link');
  css.rel = 'stylesheet'; css.href = KATEX + 'katex.min.css';
  document.head.appendChild(css);
  const font = document.createElement('link');   // marker lettering for the whiteboard
  font.rel = 'stylesheet'; font.href = WHITEBOARD_FONT;
  document.head.appendChild(font);
  return new Promise((resolve) => {
    const js = document.createElement('script');
    js.src = KATEX + 'katex.min.js';
    js.onload = js.onerror = () => resolve();
    document.head.appendChild(js);
    setTimeout(resolve, 5000);   // a slow CDN must not hold up the page; equations then show as source
  });
}

// Markdown for the voice version: KaTeX blocks, tables marked as board, no bold.
function md(text, partial = false) {
  try {
    const { md: src, blocks } = splitMath(text, partial);
    let html = DOMPurify.sanitize(marked.parse(src));
    html = markFormulaLines(stripBold(html)).replace(/<table>/g, '<table class="board">');
    return fillMath(html, blocks, renderTex);
  } catch {
    return escapeHtml(text).replace(/\n/g, '<br>');
  }
}

function buildBoard() {
  const log = document.getElementById('log');
  const wb = document.createElement('section'); wb.id = 'wb';
  wb.innerHTML = `
    <div id="wbbar">
      <div class="nav">
        <button type="button" id="prevsec" aria-label="Previous section">◀</button>
        <button type="button" id="nextsec" aria-label="Next section">▶</button>
        <select id="modsel" aria-label="Go to a module"><option value="">Go to a module</option></select>
      </div>
      <span id="wbstatus" role="status" aria-live="polite"></span>
      <div class="ctl">
        <button type="button" id="pausebtn" disabled>Pause</button>
        <button type="button" id="typebtn" aria-pressed="false">Type</button>
      </div>
    </div>
    <div id="startcard" hidden>
      <p id="startnote"></p>
      <button type="button" id="startbtn" class="primary">Start</button>
    </div>`;
  log.parentNode.insertBefore(wb, log);
  wb.insertBefore(log, wb.querySelector('#startcard'));
  const q = (s) => wb.querySelector(s);
  q('#startnote').textContent = NOTICE;
  return { wb, log, modsel: q('#modsel'), prev: q('#prevsec'), next: q('#nextsec'),
    status: q('#wbstatus'), pause: q('#pausebtn'), type: q('#typebtn'),
    startcard: q('#startcard'), startnote: q('#startnote'), start: q('#startbtn'),
    composer: document.getElementById('composer') };
}

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = src;
    s.onload = resolve;
    s.onerror = () => reject(new Error('could not load the speech detector'));
    document.head.appendChild(s);
  });
}

let vadLib = null;
function loadVad() {   // once; a failed load is tried again on the next Resume
  if (!vadLib) {
    vadLib = loadScript(ORT_CDN + 'ort.wasm.min.js')
      .then(() => loadScript(VAD_CDN + 'bundle.min.js')).then(() => window.vad);
    vadLib.catch(() => { vadLib = null; });
  }
  return vadLib;
}

export async function init(config, { isBusy, chat, synth, transcribe, isReady, notice }) {
  await loadKatex();
  const ui = buildBoard();
  if (notice) ui.startnote.textContent = notice;
  const send = document.getElementById('send');

  let ready = !!config.voice_ready;
  let started = false;   // the student pressed Start (audio unlocked, notice accepted)
  let turnActive = false, idleSent = true;

  // Listening state (functions in the listening section below).
  const idleMs = (config.idle_seconds || 45) * 1000;
  let vad = null, vadCtx = null;   // the detector and its own AudioContext
  let starting = null;   // promise while the detector opens the microphone
  let pausing = Promise.resolve();   // the last vad.pause(); start waits for it
  let stopping = false;  // api.stop() is running: its voice:idle must not open the microphone
  let listening = false; // the detector is running and its utterances are used
  let hearing = false;   // an utterance is being transcribed
  let paused = false;    // waiting at Resume (after the idle line or an error)
  let held = false;      // the student pressed Pause: audio frozen, microphone closed
  let lgen = 0;          // bumped by quiet(); stale starts and transcripts drop out
  const deadline = createIdleDeadline({ idleMs });
  let idleTimer = null;  // fires when the deadline or the segment cap may have run out
  let drained = [];      // resolvers waiting for the audio queue to empty

  // Audio. One context, resumed on the first click, tap or key.
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 1024;
  analyser.connect(ctx.destination);
  let unlock;
  const unlocked = new Promise((r) => { unlock = r; });
  const tryUnlock = () => held ? undefined : ctx.resume().then(() => { if (ctx.state === 'running') unlock(); }).catch(() => {});
  for (const ev of UNLOCK_EVENTS) document.addEventListener(ev, tryUnlock, true);
  if (ctx.state === 'running') unlock();

  let queue = [];        // promises of AudioBuffer (null = skip), in say order
  let queued = 0, spokenCount = 0;   // clips put in the queue, and clips finished (played, skipped or dropped)
  let gen = 0;           // bumped by stop(); stale loops and fetches drop out
  let playing = false;   // the playback loop is running
  let source = null;
  let speaking = false;
  let waitingUnlock = false;

  // --- the board ---------------------------------------------------------------

  let sections = [];     // section elements, oldest first
  let view = -1;         // the section on screen
  let stream = null;     // the tutor reply being streamed: {text, nodes}
  // Trees drawn after the student's last message and before the tutor's first
  // words. If those words open a new section, the trees move into it: the
  // tutor may call show_tree before it writes the section heading.
  let orphans = [], sinceStudent = true;

  // The board turns to a new section only once the voice has spoken what was
  // queued before it. Otherwise the next reply's heading would replace a
  // section, such as an intro and its list, while the voice is still reading it.
  // sec.gate: the number of clips queued when the section was made.
  const latestDue = () => lastDueSection(sections.map((sec) => sec.gate), spokenCount);
  function spoken(n = 1) {
    const follow = view === latestDue();
    spokenCount += n;
    if (follow && sections.length) { const i = latestDue(); if (i !== view) show(i); }
  }

  function newSection(title) {
    const last = sections[sections.length - 1];
    const empty = (c) => c.classList.contains('sectitle') || c.classList.contains('typing')
      || (c.classList.contains('tutor') && !c.children.length && !c.textContent.trim());
    if (last && title && [...last.children].every(empty)) {
      last.firstChild.textContent = title;   // an empty section (a title, the "thinking" line, a blank reply): reuse it
      updateNav();
      return last;
    }
    const sec = document.createElement('div'); sec.className = 'section';
    sec.gate = queued;
    const h = document.createElement('h2'); h.className = 'sectitle';
    h.textContent = title || page().subtitle || '';
    sec.appendChild(h);
    ui.log.appendChild(sec);
    const follow = view === (sections.length ? latestDue() : -1);
    sections.push(sec);
    if (follow) show(latestDue()); else updateNav();
    return sec;
  }
  function target() { return sections.length ? sections[sections.length - 1] : newSection(null); }
  function show(i) {
    view = Math.max(0, Math.min(i, sections.length - 1));
    sections.forEach((s, k) => { s.hidden = k !== view; });
    updateNav();
    scroll();
  }
  function updateNav() {
    const n = sections.length;
    ui.prev.disabled = view <= 0;
    ui.next.disabled = view >= n - 1;
  }
  function scroll() {
    if (view === sections.length - 1) ui.log.scrollTop = ui.log.scrollHeight;
    else ui.log.scrollTop = 0;
  }
  function place(el) {
    if (el.classList.contains('tree') && sinceStudent) orphans.push(el);
    target().appendChild(el);
    if (view < latestDue()) show(latestDue());   // new material: go to it, once it is due
    scroll();
    return el;
  }

  // Render a tutor reply into one or more sections. nodes: the message
  // elements already made for this reply (streaming reuses them).
  function drawTutor(text, final, nodes) {
    const parts = splitSections(text, final);
    parts.forEach((part, k) => {
      if (!nodes[k]) {
        if (part.title !== null) {
          const sec = newSection(part.title);
          if (k === 0) for (const t of orphans) if (t.isConnected && t.parentNode !== sec) sec.appendChild(t);
        }
        if (k === 0) { orphans = []; sinceStudent = false; }
        const div = document.createElement('div'); div.className = 'msg tutor';
        nodes[k] = place(div);
      }
      nodes[k].innerHTML = md(part.body, !final && k === parts.length - 1);
    });
    scroll();
  }

  function addMsg(role, text) {
    if (role === 'tutor') { const nodes = []; drawTutor(text, true, nodes); return nodes[0]; }
    const div = document.createElement('div');
    div.className = 'msg ' + role;
    div.textContent = role === 'student' ? 'You said: ' + text : text;
    if (role === 'student') { orphans = []; sinceStudent = true; }
    return place(div);
  }

  function render(display, addTree, addPlot) {
    stream = null;
    ui.log.innerHTML = ''; sections = []; view = -1; orphans = []; sinceStudent = true;
    for (const d of display) {
      if (d.role === 'tree') addTree(d.tree);
      else if (d.role === 'plot') addPlot(d.plot);
      else addMsg(d.role, d.text);
      if (d.intro) { orphans = []; sinceStudent = true; }   // as live: a tree after an intro joins the next section
    }
    if (sections.length) show(sections.length - 1);
  }

  for (const m of config.modules || []) {
    ui.modsel.add(new Option(`Module ${m.n}: ${m.title}`, String(m.n)));
  }
  ui.modsel.addEventListener('change', () => {
    const m = (config.modules || []).find((x) => String(x.n) === ui.modsel.value);
    ui.modsel.value = '';
    if (!m || !started || isBusy() || speaking || playing) return;
    place(Object.assign(document.createElement('div'),
      { className: 'msg student', textContent: `You chose Module ${m.n}: ${m.title}` }));
    orphans = []; sinceStudent = true;
    chat('', false, m.n);   // the server plays the module's fixed intro, then the tutor teaches
  });

  ui.prev.addEventListener('click', () => show(view - 1));
  ui.next.addEventListener('click', () => show(view + 1));
  ui.type.addEventListener('click', () => {
    const on = document.body.classList.toggle('typing');
    ui.type.setAttribute('aria-pressed', String(on));
    if (on) document.getElementById('msg').focus();
  });

  // --- status and playback -------------------------------------------------------

  function updateStatus() {
    let s = '';
    if (!ready) s = isReady ? 'loading the voice…' : 'Voice is unavailable right now.';
    else if (!started) s = 'press Start';
    else if (held) s = 'paused';
    else if (speaking) s = 'speaking…';
    else if (waitingUnlock) s = 'click to hear the tutor';
    else if (turnActive || hearing) s = 'thinking…';
    else if (listening) s = 'listening…';
    else if (paused && !playing) s = 'paused — press Resume';
    ui.status.textContent = s;
    ui.pause.textContent = (held || paused) ? 'Resume' : 'Pause';
    ui.pause.disabled = !ready || !started || (!held && paused && (playing || speaking));
    ui.start.disabled = !ready;
    ui.modsel.disabled = !ready || !started || turnActive || speaking || playing;
  }

  // Send is disabled while the tutor works and while its audio is playing.
  function syncSend() { send.disabled = speaking || playing || isBusy(); }

  function setSpeaking(b) {
    speaking = b;
    syncSend();
    updateStatus();
  }

  function maybeIdle() {
    if (!turnActive && !playing && !idleSent) {
      idleSent = true;
      window.dispatchEvent(new Event('voice:idle'));
    }
  }

  function settleDrained() {
    const d = drained; drained = [];
    for (const r of d) r();
  }

  function release() {   // undo Pause: unfreeze the audio
    if (!held) return;
    held = false;
    ctx.resume().catch(() => {});
  }

  function stop() {
    release();
    gen++;
    queue = [];
    spoken(queued - spokenCount);   // dropped clips count as spoken: the board catches up
    if (source) { try { source.stop(); } catch {} source = null; }
    playing = false; waitingUnlock = false;
    setSpeaking(false);
    settleDrained();
    maybeIdle();
  }

  function enqueue(p) { queue.push(p); queued++; }

  function fetchClip(n, text) {   // n: a sentence number, or 'idle'; text: what synth speaks
    const p = synth ? synth(text ?? config.idle_text ?? 'Press the button when you are ready to continue.')
      .then(({ audio, rate }) => {
        const buf = ctx.createBuffer(1, audio.length, rate);
        buf.copyToChannel(audio, 0);
        return buf;
      }) : fetch(`/api/say/${n}`).then(async (r) => {
      if (r.status === 404) return null;           // stale sentence number: skip
      if (!r.ok) throw new Error(r.status === 503 ? 'voice is not ready' : `audio error ${r.status}`);
      return ctx.decodeAudioData(await r.arrayBuffer());
    });
    p.catch(() => {});   // handled when its turn in the queue comes
    return p;
  }

  function playBuffer(buf) {
    return new Promise((resolve) => {
      const src = ctx.createBufferSource();
      src.buffer = buf; src.connect(analyser);
      src.onended = () => { if (source === src) source = null; src.disconnect(); resolve(); };
      source = src;
      src.start();
    });
  }

  async function pump() {
    playing = true;
    syncSend();
    const g = gen;
    while (queue.length) {
      const p = queue.shift();
      let buf;
      try { buf = await p; } catch (e) {
        if (g !== gen) return;
        fail(e);
        return;
      }
      if (g !== gen) return;
      if (!buf) { spoken(); continue; }
      if (ctx.state !== 'running' && !held) {
        waitingUnlock = true; updateStatus();
        await unlocked;
        if (g !== gen) return;
        waitingUnlock = false;
      }
      if (!speaking) setSpeaking(true);
      await playBuffer(buf);
      if (g !== gen) return;
      spoken();
    }
    playing = false;
    setSpeaking(false);
    settleDrained();
    maybeIdle();
  }

  // Play the idle line through the same queue. Resolves when the queue is
  // empty. A failed clip is skipped: the Resume button matters more.
  function sayIdle() {
    const done = new Promise((r) => drained.push(r));
    enqueue(fetchClip('idle').catch(() => null));
    if (!playing) pump();
    updateStatus();
    return done;
  }

  // A failed fetch or decode: tell the student and show the tutor's words for
  // the rest of this turn.
  function fail(e) {
    place(Object.assign(document.createElement('div'), { className: 'msg error',
      textContent: 'Could not play the tutor\'s voice (' + (e && e.message || 'error') + '). Showing the words instead.' }));
    document.body.classList.add('captions');
    stop();
  }

  // --- listening -------------------------------------------------------------

  function canListen() {
    return ready && started && !paused && !held && !stopping && !turnActive && !isBusy() &&
      !speaking && !playing && !hearing && !ui.composer.hidden && !document.hidden;
  }

  function mic() {
    return navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
  }

  async function createVad(audioContext) {
    const lib = await loadVad();
    return lib.MicVAD.new({
      audioContext, startOnLoad: false,
      baseAssetPath: VAD_CDN, onnxWASMBasePath: ORT_CDN,
      getStream: mic, resumeStream: mic,
      onSpeechStart: () => { if (listening) { deadline.speechStart(); schedule(); } },
      onVADMisfire: () => { if (listening) { deadline.speechEnd(); schedule(); } },
      onSpeechEnd: (audio) => { if (listening) { deadline.speechEnd(); heard(audio); } },
    });
  }

  async function listen() {
    if (listening || starting || !canListen()) return;
    const g = lgen;
    starting = (async () => {
      if (!vad) {
        const c = new AudioContext();
        try { vad = await createVad(c); vadCtx = c; } catch (e) { c.close().catch(() => {}); throw e; }
      }
      await pausing;
      await vad.start();
      await vadCtx.resume();   // allowed once the microphone is open
    })();
    try { await starting; } catch (e) {
      starting = null;
      if (g === lgen) micFailed(e);
      return;
    }
    starting = null;
    if (g !== lgen) { queueMicrotask(listen); return; }   // quiet() meanwhile: it pauses; listen again if allowed
    if (!canListen()) { quiet(false); return; }
    listening = true;
    deadline.arm();       // no-op when resuming in the same window (after an empty transcript)
    schedule();
    updateStatus();
  }

  // Stop using the microphone. destroy: also free the detector and end the
  // idle window (idle, errors, Pause, hidden tab); otherwise pause it (the
  // microphone is still released) and keep the deadline.
  function quiet(destroy) {
    lgen++;
    listening = false;
    clearIdle();
    deadline.speechEnd();
    if (destroy) deadline.disarm();
    if (starting) {
      starting.finally(() => quiet(destroy)).catch(() => {});
    } else if (vad) {
      const v = vad, c = vadCtx;
      if (destroy) {
        vad = vadCtx = null;
        v.destroy().catch(() => {}).finally(() => c.close().catch(() => {}));
      } else {
        pausing = v.pause().catch(() => {});
      }
    }
    updateStatus();
  }

  // Wait at Resume with the microphone closed.
  function hold() {
    paused = true;
    quiet(true);
  }

  function micFailed(e) {
    addMsg('error', 'Could not use the microphone (' + plain(e) + ').');
    hold();
  }

  function plain(e) { return String(e && e.message || 'error').replace(/\.$/, ''); }

  function schedule() {
    clearIdle();
    const ms = deadline.msToNext();
    if (ms !== null) idleTimer = setTimeout(checkIdle, ms);
  }
  function clearIdle() { clearTimeout(idleTimer); idleTimer = null; }

  function checkIdle() {
    idleTimer = null;
    if (!listening) return;
    if (deadline.due()) goIdle(); else schedule();
  }

  async function goIdle() {
    hold();               // the microphone closes before the tutor speaks
    await sayIdle();
    updateStatus();       // Resume is enabled now
  }

  async function heard(audio) {
    quiet(false);         // no listening while the clip is transcribed
    const g = lgen;
    hearing = true; updateStatus();
    let text = '', err = null;
    try {
      if (transcribe) text = ((await transcribe(audio)) || '').trim(); else {
      const r = await fetch('/api/listen', {
        method: 'POST', headers: { 'Content-Type': 'audio/wav' }, body: encodeWav(audio, VAD_RATE) });
      if (!r.ok) {
        let m = `error ${r.status}`;
        try { m = (await r.json()).detail || m; } catch {}
        throw new Error(m);
      }
      text = ((await r.json()).text || '').trim();
      }
    } catch (e) { err = e; }
    hearing = false;
    // Stopped meanwhile (sign out), or the student typed a message instead.
    if (g !== lgen || turnActive || isBusy()) { updateStatus(); return; }
    if (err) {
      addMsg('error', 'Could not hear that (' + plain(err) + ').');
      hold();
      return;
    }
    if (!text) {          // noise: resume in the same idle window, or stop if it has run out
      if (deadline.due() === 'idle') goIdle(); else { updateStatus(); listen(); }
      return;
    }
    deadline.transcriptSent();
    addMsg('student', text);
    chat(text, false);
  }

  ui.pause.addEventListener('click', () => {
    if (held) {                     // Resume after Pause: the tutor picks up where it stopped
      release();
      updateStatus();
      if (!playing) listen();
      return;
    }
    if (paused) {                   // Resume after the idle line or an error
      paused = false;
      updateStatus();
      listen();
      return;
    }
    held = true;                    // Pause: freeze the tutor and close the microphone
    quiet(true);
    ctx.suspend().catch(() => {});
    updateStatus();
  });

  window.addEventListener('voice:idle', () => listen());

  // A hidden tab releases the microphone; showing it again listens if allowed.
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) { if (listening || starting) quiet(true); }
    else listen();
  });

  // Start: unlocks audio (a user gesture), accepts the notice, then runs.
  let onStart = null;
  ui.start.addEventListener('click', () => {
    if (!ready) return;
    try { localStorage.setItem(NOTICE_KEY(), 'ok'); } catch {}
    started = true;
    ui.startcard.hidden = true;
    updateStatus();
    const f = onStart; onStart = null;
    if (f) f();
  });

  // Models still loading: check again until ready.
  function waitReady() {
    if (ready) return;
    if (isReady) { setTimeout(() => { if (isReady()) { ready = true; updateStatus(); } else waitReady(); }, 500); return; }
    setTimeout(() => fetch('/api/config').then((r) => r.json()).then((c) => {
      if (c.voice_ready) { ready = true; updateStatus(); } else waitReady();
    }).catch(waitReady), 3000);
  }
  waitReady();
  updateStatus();
  updateNav();

  const api = {
    md,
    addMsg,
    addNode: place,
    target,
    render,
    tutorText(delta) {
      if (!stream) stream = { text: '', nodes: [] };
      stream.text += delta;
      drawTutor(stream.text, false, stream.nodes);
    },
    afterIntro() {   // an app-played intro just ended: a tree drawn next belongs to the next section
      api.tutorEnd();
      orphans = []; sinceStudent = true;
    },
    tutorEnd() {
      if (!stream) return;
      const s = stream; stream = null;
      drawTutor(s.text, true, s.nodes);
    },
    begin(view, startChat) {   // the chat is on screen
      const run = () => { if (view.fresh) startChat(); else listen(); };
      if (started) { run(); return; }
      onStart = run;
      ui.startcard.hidden = false;
      updateStatus();
    },
    get audioBusy() { return speaking || playing; },
    onTurnStart() {
      release();        // typing a message ends a Pause
      document.body.classList.remove('captions');
      turnActive = true; idleSent = false;
      paused = false;   // typing from Resume resumes the normal loop after this turn
      quiet(false);
      deadline.disarm();   // a new idle window starts when listening resumes after this turn
      updateStatus();
    },
    onChatEvent(ev) {
      if (ev.type !== 'say' || !ready || !started) return;
      enqueue(fetchClip(ev.n, ev.text));
      if (!playing) pump();
    },
    onTurnEnd() {
      turnActive = false;
      syncSend();
      updateStatus();
      maybeIdle();
    },
    listen,
    stop() {   // the conversation is replaced (new session, sign out)
      paused = false;
      quiet(true);
      stopping = true;
      try { stop(); } finally { stopping = false; }
    },
  };
  return api;
}
