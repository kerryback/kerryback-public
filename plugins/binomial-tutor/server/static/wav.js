// WAV encoding for the student's speech: Float32 samples (-1..1) from the
// voice activity detector -> a mono 16-bit PCM WAV file, for POST /api/listen.
// Pure, so it can be tested in node.

export function encodeWav(samples, sampleRate) {
  const n = samples.length;
  const bytes = new Uint8Array(44 + 2 * n);
  const v = new DataView(bytes.buffer);
  const ascii = (at, s) => { for (let i = 0; i < s.length; i++) bytes[at + i] = s.charCodeAt(i); };
  ascii(0, 'RIFF'); v.setUint32(4, 36 + 2 * n, true); ascii(8, 'WAVE');
  ascii(12, 'fmt '); v.setUint32(16, 16, true);
  v.setUint16(20, 1, true);                 // PCM
  v.setUint16(22, 1, true);                 // mono
  v.setUint32(24, sampleRate, true);
  v.setUint32(28, sampleRate * 2, true);    // bytes per second
  v.setUint16(32, 2, true);                 // bytes per sample frame
  v.setUint16(34, 16, true);                // bits per sample
  ascii(36, 'data'); v.setUint32(40, 2 * n, true);
  for (let i = 0; i < n; i++) {
    const x = Math.max(-1, Math.min(1, samples[i] || 0));   // NaN -> 0
    v.setInt16(44 + 2 * i, x < 0 ? x * 0x8000 : x * 0x7fff, true);
  }
  return bytes;
}
