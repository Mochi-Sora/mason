import fs from 'fs';
import path from 'path';

const ROOT = path.resolve(import.meta.dirname, '..', '..');

export function getSessionId() {
  return process.env.CUSTOM_AGENT_SESSION || 'default';
}
export function readState(sessionId: string) {
  const p = path.join(ROOT, 'sessions', sessionId, 'state.md');
  try { return fs.readFileSync(p, 'utf8').slice(0, 800); } catch { return '(no state yet)'; }
}
export function readBackupStats(sessionId: string) {
  const p = path.join(ROOT, 'sessions', sessionId, 'backup.md');
  try {
    const txt = fs.readFileSync(p, 'utf8');
    const pct = Math.round((txt.length / 10_000_000) * 100);
    return { chars: txt.length, pct, display: `${(txt.length/1e6).toFixed(1)}M/10M (${pct}%)` };
  } catch { return { chars: 0, pct: 0, display: '0M/10M' }; }
}
export function readShortTermHealth() {
  const dir = path.join(ROOT, 'short_term_memories');
  try {
    const files = fs.readdirSync(dir).filter(f => f.endsWith('.md'));
    return `${files.length}/7 files`;
  } catch { return '0/7 files'; }
}
export function read1BStatus() {
  // cheap probe: check if llama-server is up
  return process.env.LLAMA_STATUS || 'idle';
}
