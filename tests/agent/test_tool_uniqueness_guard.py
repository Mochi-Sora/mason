"""Last-line tool-name uniqueness guard at the API choke point.

DeepSeek/Kimi/MiMo reject duplicate function names with HTTP 400 (#17335
class). Every upstream merge point dedupes, so a duplicate reaching the API
builder means a NEW source appeared — the guard drops it (keep-first, turn
survives) and the warning names the culprit.
"""
from agent.chat_completion_helpers import _dedupe_tool_schemas


def _t(name, tag=""):
    return {"type": "function",
            "function": {"name": name, "parameters": {}, "description": tag}}


class TestDedupeToolSchemas:
    def test_dupes_dropped_keep_first(self):
        out = _dedupe_tool_schemas([_t("a", "first"), _t("a", "second"), _t("b")])
        assert [t["function"]["name"] for t in out] == ["a", "b"]
        assert out[0]["function"]["description"] == "first"

    def test_clean_list_identical(self):
        tools = [_t("a"), _t("b")]
        assert _dedupe_tool_schemas(tools) == tools

    def test_empty_and_none(self):
        assert _dedupe_tool_schemas([]) == []
        assert _dedupe_tool_schemas(None) is None

    def test_unparseable_passthrough(self):
        assert _dedupe_tool_schemas(["junk", 42, None]) == ["junk", 42, None]
