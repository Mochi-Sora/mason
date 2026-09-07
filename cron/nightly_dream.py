"""Cron wrapper for Nightly-Dream-cycle — called at 02:00"""
import pathlib
from custom_evolution.nightly.sweep import run_nightly
from custom_memory.llm.client import LlamaClient

def main():
    base = pathlib.Path(__file__).parent.parent
    # main model client uses opencode proxy (same as agent)
    from openai import OpenAI
    try:
        main_client = OpenAI(api_key="dummy", base_url="http://127.0.0.1:8765/v1", default_headers={"HTTP-Referer": "https://mason-agent.nousresearch.com"})
        class MainWrapper:
            def complete(self, prompt, max_tokens=800, temperature=0.3):
                r = main_client.chat.completions.create(model="nemotron-3.5-lightning-free", messages=[{"role":"user","content": prompt}], max_tokens=max_tokens, temperature=temperature)
                return r.choices[0].message.content
        main = MainWrapper()
    except Exception:
        main = None
    res = run_nightly(base, llm_1b=LlamaClient(), main_client=main)
    print(res)

if __name__ == "__main__":
    main()
