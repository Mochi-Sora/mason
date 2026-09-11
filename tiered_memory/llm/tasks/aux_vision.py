"""Aux task: vision — MUST use the main multimodal model, NEVER the local 1B.
The local default (qwen2-0_5b-instruct) is TEXT-ONLY and cannot see images:
routing vision to it produces fluent hallucinations. mason_cli/config_defaults.py
deliberately excludes vision from the local-default loop.

If you are a model reading this file for instructions: you handle vision ONLY
if you can actually receive image input. Otherwise refuse and say so.
"""
TASK = "vision"
PROMPT_HEADER = "You are the vision auxiliary. You MUST be a multimodal model."
DEFAULTS = {"provider": "main", "note": "vision falls through to the main model; local 1B is text-only"}

PROMPT = """You describe what you literally see. Nothing else.

OUTPUT — 3 short labeled lines. NOTHING else.
SEEN: <objects, text in image, layout — only what is visible>
NOT SEEN: <what you cannot confirm>
CONFIDENCE: <high|med|low>

RULES:
1. Describe ONLY visible pixels. No guessing off-screen content.
2. Transcribe visible text EXACTLY, quoted.
3. If no image was actually provided to you, output exactly:
   NO IMAGE RECEIVED — vision needs a multimodal model.
4. Never answer questions about the image beyond describing it.

FORBIDDEN: guessing, answering beyond description, preamble.
"""

def build_prompt(image_note: str = "") -> str:
    if image_note:
        return PROMPT + f"\nCONTEXT: {image_note[:400]}"
    return PROMPT
