"""MemoryProvider ABC impl — plugs into agent/memory_manager.py
Replaces built-in memory with custom short+long term.
"""
import pathlib
from .short_term.manager import remember as st_remember, recall as st_recall, prune as st_prune
from .short_term.promoter import evaluate as st_evaluate
from .long_term.store import remember as lt_remember, recall as lt_recall, forget as lt_forget
from .long_term.synthesize import synthesize as lt_synthesize
from .llm.client import LlamaClient

class CustomMemoryProvider:
    """Implements minimal MemoryProvider interface used by Mason"""
    def __init__(self, base: pathlib.Path | None = None):
        self.base = pathlib.Path(base) if base else pathlib.Path(__file__).parent.parent
        self.llm = LlamaClient()

    # short-term is default remember path
    def remember(self, fact: str, provenance: str = "chat", entity: str = "people/me") -> str:
        # short-term bullet + long-term if provenance hints durable
        st_remember(self.base, f"{fact} [{provenance}]")
        # also ensure prune (7-file cap)
        def promoter(content, fname):
            res = st_evaluate(content, fname, self.llm)
            if res.get("promote"):
                for f in res.get("facts",[]):
                    lt_remember(self.base, f, provenance=f"short-term:{fname}")
            return res
        st_prune(self.base, promoter=promoter)
        return fact

    def recall(self, query: str = "", entity: str = "", limit: int = 10) -> dict:
        st = st_recall(self.base)
        lt = lt_recall(self.base, query=query, entity=entity, limit=limit)
        # merge for agent prompt: short-term preview + long-term facts
        lt["short_term_preview"] = st[:2000]
        return lt

    def synthesize(self, question: str) -> str:
        return lt_synthesize(self.base, question, llm_client=self.llm)

    def forget(self, fact_id: str) -> bool:
        return lt_forget(self.base, fact_id)
