# Custom Memory — wiring

## Install llama.cpp 1B (global)

```bash
# 1) Fetch 1B GGUF (~400MB)
mkdir -p custom_memory/llm/models
wget -O custom_memory/llm/models/qwen2-0_5b-instruct-q4_k_m.gguf \
  https://huggingface.co/Qwen/Qwen2-0.5B-Instruct-GGUF/resolve/main/qwen2-0_5b-instruct-q4_k_m.gguf

# 2a) Option A — llama-server (recommended, global HTTP)
# Build from https://github.com/ggerganov/llama.cpp
llama-server --model custom_memory/llm/models/qwen2-0_5b-instruct-q4_k_m.gguf --port 8080 --threads 2 --ctx-size 2048

# 2b) Option B — python binding
pip install llama-cpp-python
python -c "from llama_cpp import Llama; Llama(model_path='custom_memory/llm/models/qwen2-0_5b-instruct-q4_k_m.gguf')"
```

## Use

```python
from custom_memory.provider import CustomMemoryProvider
m = CustomMemoryProvider()
m.remember("Marco prefers potatoes", provenance="chat 2026-09-06")
print(m.recall(query="potatoes"))
print(m.synthesize("what does Marco like?"))
```

## Behavior

- 7 files × 3000 chars, bullet-only, auto-prune with LLM promoter
- Long-term = Gbrain-inspired: pages + facts.jsonl + FTS5 + deterministic graph (no dream cycle)
- `llama.cpp` is global — any agent code can `from custom_memory.llm.client import LlamaClient`
```
