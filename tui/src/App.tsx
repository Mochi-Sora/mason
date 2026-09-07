import React, {useState, useEffect, useRef} from 'react';
import {Box, Text} from 'ink';
import TextInput from 'ink-text-input';
import {readState, readBackupStats, readShortTermHealth, getSessionId} from './state.js';
import {bridge} from './bridge.js';

export default function App() {
  const sessionId = getSessionId();
  const [input, setInput] = useState('');
  const [state, setState] = useState(readState(sessionId));
  const [backup, setBackup] = useState(readBackupStats(sessionId));
  const [st, setSt] = useState(readShortTermHealth());
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const [log, setLog] = useState<string[]>(['Welcome to Mason — State-First TUI', 'Type a message to chat (live loop), /recall <q>, /state, /close']);

  useEffect(() => {
    const id = setInterval(() => {
      setState(readState(sessionId));
      setBackup(readBackupStats(sessionId));
      setSt(readShortTermHealth());
    }, 2000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => () => bridge.stop(), []);

  const push = (lines: string[]) => setLog(l => [...l, ...lines].slice(-40));

  const onSubmit = (v: string) => {
    const msg = v.trim();
    setInput('');
    if (!msg || busyRef.current) return;
    if (msg.startsWith('/recall ')) {
      const q = msg.slice(8);
      push([`> ${msg}`, `(recall: query backup.md FTS for "${q}" — wired to sessions/container.py:recall_backup)`]);
      return;
    }
    if (msg === '/state') {
      push([`> ${msg}`, state]);
      return;
    }
    if (msg === '/close') {
      busyRef.current = true;
      setBusy(true);
      push([`> ${msg}`, '◌ closing session (promote + purge)…']);
      bridge.send('close', {session_id: sessionId}).then(
        r => push([r.ok ? '◆ session closed — facts promoted, folder purged.' : `✗ close failed: ${r.error}`]),
        e => push([`✗ close failed: ${e.message}`]),
      ).finally(() => {
        busyRef.current = false;
        setBusy(false);
      });
      return;
    }
    // Live turn through tui/bridge.py -> agent/conversation_loop.py
    busyRef.current = true;
    setBusy(true);
    push([`> ${msg}`, '◌ thinking…']);
    bridge.send('chat', {session_id: sessionId, message: msg}).then(
      r => {
        setLog(l => {
          const trimmed = l[l.length - 1] === '◌ thinking…' ? l.slice(0, -1) : l;
          const body = r.ok ? (r.reply || '(empty reply)') : `✗ ${r.error || 'failed'}`;
          return [...trimmed, `◈ ${body}`].slice(-40);
        });
      },
      e => {
        setLog(l => {
          const trimmed = l[l.length - 1] === '◌ thinking…' ? l.slice(0, -1) : l;
          return [...trimmed, `✗ bridge error: ${e.message}`].slice(-40);
        });
      },
    ).finally(() => {
      busyRef.current = false;
      setBusy(false);
    });
  };

  return (
    <Box flexDirection="column">
      <Box borderStyle="round" borderColor="cyan" paddingX={1}>
        <Text bold color="cyan">◈ Mason</Text>
        <Text>  session:{sessionId}  {busy ? '◌ working' : 'idle'} | backup:{backup.display} | short-term:{st}</Text>
      </Box>
      <Box flexDirection="column" borderStyle="single" paddingX={1} marginTop={1}>
        <Text dimColor>state.md (tiny, 90% cut):</Text>
        <Text>{state.slice(0, 200)}</Text>
        <Box marginTop={1} flexDirection="column">
          {log.slice(-8).map((l, i) => <Text key={i}>{l}</Text>)}
        </Box>
      </Box>
      <Box marginTop={1}>
        <Text color="green">› </Text>
        <TextInput value={input} onChange={setInput} onSubmit={onSubmit} placeholder={busy ? 'working…' : 'message  /recall <q>  /state  /close'} />
      </Box>
      <Box marginTop={1}>
        <Text dimColor>Live loop via tui/bridge.py | /close promotes + purges the session</Text>
      </Box>
    </Box>
  );
}
