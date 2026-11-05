// Idle deadline for hands-free listening. Pure logic, no timers or DOM.
//
// One deadline per listening window: arm() sets it idleMs ahead if it is not
// already set, so listening that resumes after a VAD misfire or an empty
// transcript keeps the same deadline. Only a sent transcript (transcriptSent)
// or disarm() clears it; the next arm() then starts a new window. Speech start
// does not move it, so background noise cannot hold the microphone open.
//
// A speech segment is also capped at MAX_SEGMENT_MS (the server refuses longer
// clips), so continuous noise cannot hold the microphone either.
//
//   arm()            listening starts (after a tutor turn, Continue, or a resume)
//   disarm()         the microphone is released for good (idle, Text, errors, a turn)
//   transcriptSent() a non-empty transcript went to the tutor
//   speechStart()    the detector heard the start of speech
//   speechEnd()      the segment ended (speech end or misfire)
//   due()            'idle' | 'segment' | null: what has run out now
//   msToNext()       ms until the next thing can run out, or null

export const MAX_SEGMENT_MS = 60000;   // speech.py MAX_CLIP_SECONDS

export function createIdleDeadline({ idleMs, maxSegmentMs = MAX_SEGMENT_MS, now = () => Date.now() }) {
  let deadline = null;   // ms timestamp, or null when not armed
  let segStart = null;   // ms timestamp of the current speech start, or null

  const disarm = () => { deadline = null; segStart = null; };
  return {
    arm() { if (deadline === null) deadline = now() + idleMs; },
    disarm,
    transcriptSent: disarm,
    speechStart() { segStart = now(); },
    speechEnd() { segStart = null; },
    due() {
      const t = now();
      if (deadline !== null && t >= deadline) return 'idle';
      if (segStart !== null && t - segStart >= maxSegmentMs) return 'segment';
      return null;
    },
    msToNext() {
      const t = now(), ends = [];
      if (deadline !== null) ends.push(deadline - t);
      if (segStart !== null) ends.push(segStart + maxSegmentMs - t);
      return ends.length ? Math.max(0, Math.min(...ends)) : null;
    },
  };
}
