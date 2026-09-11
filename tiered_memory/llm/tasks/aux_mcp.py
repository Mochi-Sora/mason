"""Aux task: mcp — default to local 1B (llama.cpp)
Called by: agent/auxiliary_client.py get_text_auxiliary_client(task="mcp").
Route: provider=local, base_url=http://127.0.0.1:8080, model=qwen2-0_5b.
Job: map ONE user request to the right MCP server + tool + args skeleton.
"""
TASK = "mcp"
PROMPT_HEADER = "You are the mcp auxiliary."
DEFAULTS = {"provider": "local", "base_url": "http://127.0.0.1:8080", "model": "qwen2-0_5b-instruct", "timeout": 30}
PROMPT = """You route one request to an MCP tool. Nothing else.

REQUEST:
{request}

AVAILABLE SERVERS AND TOOLS:
{servers}

OUTPUT — JSON object. NOTHING else. No fences. No explanation.
{{"server": "name", "tool": "name", "args": {{"key": "value"}}, "reason": "one short sentence"}}

RULES:
1. Pick the tool whose description matches the request best. Name it EXACTLY.
2. args: fill ONLY keys you know from the request; unknown keys → "".
3. No suitable tool → {{"server": "", "tool": "", "args": {{}}, "reason": "no match: <why>"}}.
4. Never invent server or tool names. Copy from the list above.

EXAMPLE:
REQUEST: read my latest email
SERVERS: gmail(send, read), calendar(list)
OUTPUT: {{"server": "gmail", "tool": "read", "args": {{"count": "1"}}, "reason": "read matches latest-email request"}}

FORBIDDEN: markdown, fences, invented names, commentary.
"""

def build_prompt(request: str, servers: str = "") -> str:
    return PROMPT.format(request=request[:800], servers=servers[:1500])
