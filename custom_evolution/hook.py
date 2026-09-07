"""Hook to call after every agent final_response — fire-and-forget Avg-evo
Usage: from custom_evolution.hook import on_response; on_response(user_msg, final_response, tool_trace)
"""
import pathlib, threading

def on_response(base: pathlib.Path | None, user_msg: str, final_response: str, tool_trace: str = ""):
    base = pathlib.Path(base) if base else pathlib.Path(__file__).parent.parent
    try:
        from custom_memory.llm.client import LlamaClient
        from custom_evolution.avg_evo.analyzer import handle_response
        llm = LlamaClient()
        # fire-and-forget so user not blocked; timeout 800ms inside analyzer
        def _run():
            try:
                handle_response(base, user_msg, final_response, tool_trace, llm_client=llm)
            except Exception:
                pass
        t = threading.Thread(target=_run, daemon=True)
        t.start()
    except Exception:
        pass
