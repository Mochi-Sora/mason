"""Custom memory provider — wraps custom_memory/provider.py"""
from custom_memory.provider import CustomMemoryProvider as _Base
from agent.memory_provider import MemoryProvider

class CustomProvider(MemoryProvider):
    name = "custom"
    def __init__(self, *a, **kw):
        self._base = _Base(*a, **kw)
    def initialize(self, *a, **kw):
        return self._base.initialize(*a, **kw) if hasattr(self._base, 'initialize') else None
    def system_prompt_block(self, *a, **kw):
        # short-term preview is already via custom_memory, keep empty here
        return ""
    def prefetch(self, query: str, **kw):
        res = self._base.recall(query=query)
        facts = res.get("facts", [])
        return "\n".join(f"- {f['fact']}" for f in facts[:5]) if facts else ""
    def handle_tool_call(self, name: str, args: dict):
        if name == "memory":
            return self._base.recall(**args)
        return None
