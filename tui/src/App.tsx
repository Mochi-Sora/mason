import React, {useState, useEffect, useRef} from 'react';
import {Box, Text, useInput} from 'ink';
import TextInput from 'ink-text-input';
import {readState, readBackupStats, readShortTermHealth, getSessionId} from './state.js';
import {bridge} from './bridge.js';

const PAGE = 8;

export default function App() {
  const sessionId = getSessionId();
  const [input, setInput] = useState('');
  const [state, setState] = useState(readState(sessionId));
  const [backup, setBackup] = useState(readBackupStats(sessionId));
  const [st, setSt] = useState(readShortTermHealth());
  const [busy, setBusy] = useState(false);
  const [stream, setStream] = useState('');
  const [scroll, setScroll] = useState(0); // lines up from the live bottom
  const [deaths, setDeaths] = useState(0); // bridge respawn counter
  const busyRef = useRef(false);
  const [log, setLog] = useState<string[]>([
    'Welcome to Mason — State-First TUI',
    'Chat streams live. PgUp/PgDn scrolls. /stop interrupts. /close promotes + purges.',
  ]);

  useEffect(() => {
    const id = setInterval(() => {
      setState(readState(sessionId));
      setBackup(readBackupStats(sessionId));
      setSt(readShortTermHealth());
      if (!bridge.alive()) setDeaths(bridge.starts);
    }, 2000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => () => bridge.stop(), []);

  useInput((ch, key) => {
    if (key.pageUp) setScroll(s => Math.min(s + PAGE, 192));
    else if (key.pageDown) setScroll(s => Math.max(s - PAGE, 0));
  });

  const push = (lines: string[]) => {
    setLog(l => [...l, ...lines].slice(-200));
    setScroll(0);
  };

  const finishTurn = (finalLine: string) => {
    setStream('');
    push([finalLine]);
    busyRef.current = false;
    setBusy(false);
  };

  const onSubmit = (v: string) => {
    const msg = v.trim();
    setInput('');
    if (!msg) return;
    if (msg.startsWith('/recall ')) {
      const q = msg.slice(8);
      push([`> ${msg}`, `(recall: query backup.md FTS for "${q}" — wired to sessions/container.py:recall_backup)`]);
      return;
    }
    if (msg === '/state') {
      push([`> ${msg}`, state]);
      return;
    }
    if (msg === '/stop') {
      if (!busyRef.current) {
        push(['(nothing running)']);
        return;
      }
      bridge.send('stop', {session_id: sessionId}).then(
        r => push([r.ok ? '■ stopped.' : `✗ stop failed: ${r.error}`]),
        e => push([`✗ stop failed: ${e.message}`]),
      );
      return;
    }
    if (msg === '/close') {
      if (busyRef.current) {
        push(['(turn running — /stop first, then /close)']);
        return;
      }
      busyRef.current = true;
      setBusy(true);
      push([`> ${msg}`, '◌ closing session (promote + purge)…']);
      bridge.send('close', {session_id: sessionId}).then(
        r => finishTurn(r.ok ? '◆ session closed — facts promoted, folder purged.' : `✗ close failed: ${r.error}`),
        e => finishTurn(`✗ close failed: ${e.message}`),
      );
      return;
    }
    if (busyRef.current) return;
    // Live streaming turn through tui/bridge.py -> agent/conversation_loop.py
    busyRef.current = true;
    setBusy(true);
    setStream('');
    setLog(l => [...l, `> ${msg}`].slice(-200));
    bridge.send('chat', {session_id: sessionId, message: msg}, c => {
      setStream(s => (s + c).slice(-4000));
    }).then(
      r => {
        if (r.started) return; // ack only — chunks + final arrive separately
        if (r.ok) finishTurn(`◈ ${(r.reply || '').trim() || '(empty reply)'}`);
        else finishTurn(`✗ ${r.error || 'failed'}`);
      },
      e => finishTurn(`✗ bridge error: ${e.message} (retry sends respawn it)`),
    );
  };

  const tail = log.slice(-PAGE - Math.min(scroll, Math.max(0, log.length - PAGE)));
  const view = scroll > 0 ? [...tail, `(▲ ${scroll} lines up — PgDn to return)`] : tail;

  return (
    <Box flexDirection="column">
      <Box borderStyle="round" borderColor="cyan" paddingX={1}>
        <Text bold color="cyan">◈ Mason</Text>
        <Text>
          {'  '}session:{sessionId} {busy ? '◌ working (/stop)' : 'idle'} | backup:{backup.display} | short-term:{st}
          {deaths > 1 ? ` | bridge↻${deaths}` : ''}
        </Text>
      </Box>
      <Box flexDirection="column" borderStyle="single" paddingX={1} marginTop={1}>
        <Text dimColor>state.md (tiny, 90% cut):</Text>
        <Text>{state.slice(0, 200)}</Text>
        <Box marginTop={1} flexDirection="column">
          {view.map((l, i) => <Text key={i}>{l}</Text>)}
          {stream ? <Text color="gray">◈ {stream.slice(-600)}</Text> : null}
        </Box>
      </Box>
      <Box marginTop={1}>
        <Text color="green">› </Text>
        <TextInput
          value={input}
          onChange={setInput}
          onSubmit={onSubmit}
          placeholder={busy ? 'working… (/stop)' : 'message  /recall <q>  /state  /stop  /close'}
        />
      </Box>
      <Box marginTop={1}>
        <Text dimColor>Live loop via tui/bridge.py (streaming) | PgUp/PgDn scrolls history</Text>
      </Box>
    </Box>
  );
}
