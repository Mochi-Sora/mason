"""Hook: fire Avg-evo after every agent final_response — fire-and-forget.

Usage: from custom_evolution.hook import on_response
       on_response(base, user_msg, final_response, tool_trace="", messages=None)

Respects custom_evolution/config.yaml avg_evo.enabled. Timeout comes from
config timeout_ms, clamped to ≥15s (an 800ms cap would turn every CPU-1B call
into a no-op); the thread is daemonic and never blocks the turn either way.
"""
import functools
import pathlib
import re
import threading

_CONFIG_CACHE: dict = {}


def _config(base: pathlib.Path) -> dict:
    key = str(base)
    if key not in _CONFIG_CACHE:
        cfg: dict = {}
        try:
            text = (base / "custom_evolution" / "config.yaml").read_text()
            m = re.search(r"avg_evo:\s*\n((?:[ \t]+\S.*\n?)+)", text)
            if m:
                for line in m.group(1).splitlines():
                    kv = re.match(r"\s*(\w+)\s*:\s*(.+?)\s*$", line)
                    if kv:
                        cfg[kv.group(1)] = kv.group(2)
        except OSError:
            pass
        _CONFIG_CACHE[key] = cfg
    return _CONFIG_CACHE[key]


def _trace_from_messages(messages, limit: int = 3) -> str:
    """Last N tool results, compacted — what the 1B actually needs to see."""
    if not messages:
        return ""
    bits = []
    for m in reversed(messages):
        if not isinstance(m, dict):
            continue
        if m.get("role") == "tool":
            content = str(m.get("content", ""))[:400]
            bits.append(f"{m.get('name', 'tool')}: {content}")
        elif m.get("tool_calls"):
            try:
                names = [tc["function"]["name"] for tc in m["tool_calls"]]
                bits.append("called: " + ", ".join(names))
            except Exception:
                continue
        if len(bits) >= limit:
            break
    return "\n".join(reversed(bits))


def on_response(base: pathlib.Path | None, user_msg: str, final_response: str,
                tool_trace: str = "", messages=None):
    base = pathlib.Path(base) if base else pathlib.Path(__file__).parent.parent
    try:
        cfg = _config(base)
        if str(cfg.get("enabled", "true")).lower() not in ("1", "true", "yes", "on"):
            return
        timeout = max(15, int(str(cfg.get("timeout_ms", "45000"))) // 1000)
    except Exception:
        timeout = 45
    if not tool_trace and messages:
        try:
            tool_trace = _trace_from_messages(messages)
        except Exception:
            tool_trace = ""
    try:
        from custom_memory.llm.client import LlamaClient
        from custom_evolution.avg_evo.analyzer import handle_response
        llm = LlamaClient()

        def _run():
            try:
                handle_response(base, str(user_msg or "")[:800],
                                str(final_response or "")[:1200],
                                str(tool_trace or "")[:800],
                                llm_client=llm, timeout=timeout)
            except Exception:
                pass
        threading.Thread(target=_run, daemon=True,
                         name="avg-evo").start()
    except Exception:
        pass
