"""Thin wrapper around the Anthropic API. All modules route LLM calls through here."""
import json
import re

import config

_client = None


def client():
    global _client
    if _client is None:
        if not config.ANTHROPIC_API_KEY:
            msg = "ANTHROPIC_API_KEY missing. Add it to .env — get a key at https://console.anthropic.com"
            if config.ENV_WARNING:
                msg += "\n\nLikely cause: " + config.ENV_WARNING
            raise RuntimeError(msg)
        from anthropic import Anthropic
        _client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


def ask(prompt: str, system: str = "", max_tokens: int = 3000, model: str = "") -> str:
    """Single-turn text completion with brand context always injected.
    `model` overrides the configured default (subagents declare their own)."""
    sys_prompt = f"{system}\n\nBRAND CONTEXT:\n{config.BRAND_CONTEXT}".strip()
    resp = client().messages.create(
        model=model or config.CLAUDE_MODEL,
        max_tokens=max_tokens,
        system=sys_prompt,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in resp.content if b.type == "text")


def ask_json(prompt: str, system: str = "", max_tokens: int = 3000, model: str = ""):
    """Completion that must return JSON. Strips fences and parses."""
    sys_prompt = (
        f"{system}\n\nRespond with ONLY valid JSON. No prose, no markdown fences."
    )
    raw = ask(prompt, system=sys_prompt, max_tokens=max_tokens, model=model)
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Attempt to salvage the first JSON object/array in the output
        m = re.search(r"[\[{].*[\]}]", cleaned, flags=re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise


def chat(messages: list[dict], system: str = "") -> str:
    """Multi-turn chat with brand context. Shared by CLI chat and GUI chat."""
    sys_prompt = f"{system}\n\nBRAND CONTEXT:\n{config.BRAND_CONTEXT}".strip()
    resp = client().messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=2000,
        system=sys_prompt,
        messages=messages[-20:],
    )
    return "".join(b.text for b in resp.content if b.type == "text")


def ask_with_images(prompt: str, image_paths: list, system: str = "",
                    max_tokens: int = 4000, model: str = "") -> str:
    """Single-turn completion that includes images (JPEG/PNG frames).

    Used by the video analyzer: frames extracted to disk are read back,
    base64-encoded, and sent alongside the prompt so Claude actually sees them.
    Images are capped to protect the token budget and the API's per-request limit.
    """
    import base64
    import mimetypes

    sys_prompt = f"{system}\n\nBRAND CONTEXT:\n{config.BRAND_CONTEXT}".strip()

    content = []
    MAX_IMAGES = 40  # hard ceiling regardless of caller
    for p in list(image_paths)[:MAX_IMAGES]:
        try:
            data = open(p, "rb").read()
        except OSError:
            continue
        media_type = mimetypes.guess_type(str(p))[0] or "image/jpeg"
        if media_type not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
            media_type = "image/jpeg"
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": base64.standard_b64encode(data).decode("ascii"),
            },
        })
    content.append({"type": "text", "text": prompt})

    resp = client().messages.create(
        model=model or config.CLAUDE_MODEL,
        max_tokens=max_tokens,
        system=sys_prompt,
        messages=[{"role": "user", "content": content}],
    )
    return "".join(b.text for b in resp.content if b.type == "text")
