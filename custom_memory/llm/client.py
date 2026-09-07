"""Global llama.cpp 1B client — used by memory + any agent turn
- Prefers llama-server @ 127.0.0.1:8080 (OpenAI-compatible)
- Falls back to llama_cpp python binding if server down
- Falls back to no-op if model missing
"""
import os, pathlib, json, urllib.request

CONFIG_PATH = pathlib.Path(__file__).parent / "config.yaml"
DEFAULT_MODEL = "models/qwen2-0_5b-instruct-q4_k_m.gguf"  # ~400MB

class LlamaClient:
    def __init__(self, model_path: str = "", base_url: str = "http://127.0.0.1:8080",
                 model: str = ""):
        self.model_path = model_path or str(pathlib.Path(__file__).parent / DEFAULT_MODEL)
        self.base_url = base_url.rstrip("/")
        # Server-side model selector (ollama-style backends REQUIRE it;
        # llama-server harmlessly ignores it). Env-overridable for cron.
        self.model = model or os.environ.get("MASON_1B_MODEL", "")
        if not base_url or base_url == "http://127.0.0.1:8080":
            env_url = os.environ.get("MASON_1B_URL", "")
            if env_url:
                self.base_url = env_url.rstrip("/")
        self._llama = None

    def _try_server(self, prompt: str, max_tokens=256, temperature=0.2, stop=None,
                    timeout: int = 10) -> str | None:
        url = f"{self.base_url}/v1/completions"
        # Default stop (blank line) keeps JSON one-liners tight; multi-paragraph
        # tasks (nightly report) must pass stop=[] or lose everything past ¶1.
        body: dict = {"prompt": prompt, "max_tokens": max_tokens, "temperature": temperature,
                      "stop": ["\n\n"] if stop is None else stop}
        if self.model:
            body["model"] = self.model
        try:
            req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                j = json.loads(r.read().decode())
                if "choices" in j:
                    return j["choices"][0].get("text","")
                return j.get("content","")
        except Exception:
            return None

    def _try_python(self, prompt: str, max_tokens=256, temperature=0.2) -> str | None:
        try:
            from llama_cpp import Llama
            if self._llama is None:
                if not pathlib.Path(self.model_path).exists():
                    return None
                self._llama = Llama(model_path=self.model_path, n_ctx=2048, n_threads=2, verbose=False)
            out = self._llama(prompt, max_tokens=max_tokens, temperature=temperature, stop=["\n\n"])
            return out["choices"][0]["text"]
        except Exception:
            return None

    def complete(self, prompt: str, max_tokens=256, temperature=0.2, stop=None,
                 timeout: int = 10) -> str:
        # 1) server
        r = self._try_server(prompt, max_tokens, temperature, stop, timeout)
        if r:
            return r
        # 2) python binding
        r = self._try_python(prompt, max_tokens, temperature)
        if r:
            return r
        # 3) fallback: echo truncated prompt (safe no-op)
        return '{"promote": false, "facts": [], "reason": "llm unavailable — fallback"}'

    def health(self) -> dict:
        return {"model_path": self.model_path, "exists": pathlib.Path(self.model_path).exists(), "server": self.base_url}
