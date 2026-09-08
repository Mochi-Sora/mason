import {spawn, ChildProcess} from 'node:child_process';
import {join, dirname} from 'node:path';
import {fileURLToPath} from 'node:url';

type Pending = {
  resolve: (v: any) => void;
  reject: (e: Error) => void;
  onChunk?: (text: string) => void;
};

// stdio JSON-RPC client for tui/bridge.py (one JSON object per line).
// Auto-respawns the bridge if it dies; chunk lines stream into onChunk.
export class Bridge {
  private proc: ChildProcess | null = null;
  private nextId = 1;
  private pending = new Map<number, Pending>();
  private buf = '';
  starts = 0; // times the bridge process was spawned (reconnect signal)

  private root(): string {
    // src/bridge.ts -> tui/bridge.py
    return join(dirname(fileURLToPath(import.meta.url)), '..', 'bridge.py');
  }

  start(python = 'python3'): void {
    if (this.proc) return;
    this.starts += 1;
    this.proc = spawn(python, [this.root()], {stdio: ['pipe', 'pipe', 'inherit']});
    this.proc.stdout!.on('data', (d: Buffer) => this.onData(d.toString()));
    this.proc.on('exit', () => {
      this.proc = null; // next send() respawns (reconnect)
      for (const [, p] of this.pending) p.reject(new Error('bridge exited — retry sends respawn it'));
      this.pending.clear();
    });
  }

  alive(): boolean {
    return this.proc !== null;
  }

  private onData(chunk: string): void {
    this.buf += chunk;
    let nl: number;
    while ((nl = this.buf.indexOf('\n')) >= 0) {
      const line = this.buf.slice(0, nl).trim();
      this.buf = this.buf.slice(nl + 1);
      if (!line) continue;
      let msg: any;
      try {
        msg = JSON.parse(line);
      } catch {
        continue; // partial line — wait for more
      }
      const p = this.pending.get(msg.id);
      if (!p) continue;
      if (typeof msg.chunk === 'string' && !('ok' in msg)) {
        p.onChunk?.(msg.chunk);
        continue;
      }
      this.pending.delete(msg.id);
      p.resolve(msg);
    }
  }

  send(op: string, extra: Record<string, any> = {}, onChunk?: (text: string) => void): Promise<any> {
    this.start();
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      this.pending.set(id, {resolve, reject, onChunk});
      try {
        this.proc!.stdin!.write(JSON.stringify({id, op, ...extra}) + '\n');
      } catch (e) {
        this.pending.delete(id);
        reject(e instanceof Error ? e : new Error(String(e)));
      }
      setTimeout(() => {
        if (this.pending.delete(id)) reject(new Error('bridge timeout (10 min)'));
      }, 600_000).unref?.();
    });
  }

  stop(): void {
    try {
      this.proc?.kill();
    } catch {
      /* already gone */
    }
    this.proc = null;
  }
}

export const bridge = new Bridge();
