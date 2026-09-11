import pathlib
BASE = pathlib.Path(__file__).parent.parent
SHORT_DIR = BASE / "short_term_memories"
LONG_DIR = BASE / "long_term_memories"
LLM_CONFIG = BASE / "tiered_memory" / "llm" / "config.yaml"
