"""Subagent loader.

Reads Claude Code style agent definition files (markdown with YAML-ish
frontmatter) from the `agents/` folder and runs them as specialist personas
against a task, with your brand context and live data injected.

File format:

    ---
    name: content-marketer
    description: "When to use this agent"
    tools: Read, Write, WebSearch
    model: haiku
    ---

    <the system prompt body>

Notes on fidelity: these files were written for Claude Code, where the agent
can actually call the listed tools. Here the body is used as a system prompt
and the agent answers from the brand context plus whatever live data the
the connectors provide — it cannot read your filesystem or browse. The
`tools:` line is parsed and reported so the difference is visible, not hidden.
"""
import re
from pathlib import Path

import config
import llm

AGENTS_DIR = Path(__file__).parent.parent / "agents"

# Friendly model names in frontmatter -> current Claude API model strings.
MODEL_MAP = {
    "haiku": "claude-haiku-4-5",
    "sonnet": "claude-sonnet-5",
    "opus": "claude-opus-5",
    "fable": "claude-fable-5",
    "inherit": "",   # use the agent's configured default
}


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Return (metadata, body). Tolerant of unquoted values and colons inside
    quoted strings, so we don't need a YAML dependency."""
    meta: dict = {}
    if not text.startswith("---"):
        return meta, text.strip()
    parts = text.split("---", 2)
    if len(parts) < 3:
        return meta, text.strip()
    raw, body = parts[1], parts[2]
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        meta[key.strip().lower()] = value
    return meta, body.strip()


def load(name: str) -> dict | None:
    """Load one subagent by name (with or without .md)."""
    stem = name[:-3] if name.endswith(".md") else name
    path = AGENTS_DIR / f"{stem}.md"
    if not path.exists():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # Don't let one bad file break `agents` listing; salvage what we can.
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    meta, body = _parse_frontmatter(raw)
    return {
        "name": meta.get("name", stem),
        "description": meta.get("description", ""),
        "tools": [t.strip() for t in meta.get("tools", "").split(",") if t.strip()],
        "model": meta.get("model", "inherit"),
        "prompt": body,
        "path": path,
    }


def available() -> list[dict]:
    """All installed subagents, sorted by name."""
    if not AGENTS_DIR.exists():
        return []
    out = []
    for p in sorted(AGENTS_DIR.glob("*.md")):
        try:
            a = load(p.stem)
        except Exception as e:
            print(f"[subagents] skipping {p.name}: {e}")
            continue
        if a and a["prompt"]:
            out.append(a)
    return out


def list_agents() -> str:
    agents = available()
    if not agents:
        return (
            f"No subagents installed.\n"
            f"Drop Claude Code style .md agent files into: {AGENTS_DIR}"
        )
    lines = ["INSTALLED SUBAGENTS", "=" * 46]
    for a in agents:
        model = MODEL_MAP.get(a["model"], a["model"]) or config.CLAUDE_MODEL
        desc = a["description"][:150] + ("…" if len(a["description"]) > 150 else "")
        lines.append(f"\n{a['name']}  [{model}]")
        if desc:
            lines.append(f"  {desc}")
        if a["tools"]:
            lines.append(f"  declared tools: {', '.join(a['tools'])}  (not executable here)")
    lines.append(f'\nRun one:  python agent.py run-agent {agents[0]["name"]} "your task"')
    return "\n".join(lines)


def _live_context() -> str:
    """Real data the subagent should know about, best effort and never fatal."""
    bits = []
    try:
        from connectors import posts as posts_src
        p = posts_src.fetch_all()
        if p:
            bits.append(f"{len(p)} recent posts available across Instagram/TikTok.")
    except Exception:
        pass
    try:
        from connectors import klaviyo
        if klaviyo.available():
            bits.append(f"Klaviyo list size: {klaviyo.total_count():,} subscribers.")
    except Exception:
        pass
    try:
        from modules import competitors
        logged = competitors.load_logged_posts()
        if logged:
            bits.append(f"{len(logged)} competitor posts logged for reference.")
    except Exception:
        pass
    return ("\nCURRENT DATA:\n- " + "\n- ".join(bits)) if bits else ""


def _roster(exclude: str = "") -> str:
    """The other subagents actually installed. Coordinator-style agents reference
    teammates by name, so give them the real roster instead of letting them
    invent one."""
    others = [a for a in available() if a["name"] != exclude]
    if not others:
        return ""
    lines = [f"- {a['name']}: {a['description'][:120]}" for a in others]
    return (
        "\n\nSUBAGENTS ACTUALLY INSTALLED (the only ones that exist here — do not "
        "reference teammates that are not on this list):\n" + "\n".join(lines)
        + "\nThey are invoked by the operator with: python agent.py run-agent <name> \"<task>\""
    )


def run(name: str, task: str) -> str:
    agent = load(name)
    if not agent:
        names = ", ".join(a["name"] for a in available()) or "none installed"
        return f"No subagent named '{name}'. Available: {names}"
    if not task.strip():
        return (
            f"Give {agent['name']} something to do, e.g.\n"
            f'  python agent.py run-agent {agent["name"]} "plan drop week content"'
        )

    system = agent["prompt"]
    if agent["tools"]:
        system += (
            "\n\nIMPORTANT ENVIRONMENT NOTE: you are running inside CB Agent, "
            "not Claude Code. You cannot call tools, read files, or browse the web. "
            "Work from the brand context and data provided below. If a step genuinely "
            "requires data you do not have, say so plainly and state what to gather "
            "rather than inventing numbers."
        )

    model = MODEL_MAP.get(agent["model"], agent["model"]) or config.CLAUDE_MODEL
    return llm.ask(
        f"TASK: {task}{_live_context()}{_roster(exclude=agent['name'])}",
        system=system,
        max_tokens=4000,
        model=model,
    )
