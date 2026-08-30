"""Site module: edit the Shopify theme in natural language, get improvement ideas.

Flow for an edit:
  1. You describe the change ("make the countdown timer bigger on mobile")
  2. Agent picks the relevant theme file(s) from the asset list (or you name one)
  3. Claude rewrites the complete file (full replacement, never a diff)
  4. Original is backed up locally; new version written to the DRAFT theme
  5. You get a preview link — live site untouched until you publish

Publishing to live is a separate, explicit step.
"""
import json

import llm
from connectors import themes

# Files the improvement scan reads (kept small to control tokens)
IDEA_FILES = [
    "config/settings_data.json",
    "templates/index.json",
    "sections/drop-hero.liquid",
]


def _scope_guard(fn):
    """Turn a Shopify theme-scope denial into a clean message, not a crash."""
    import functools

    @functools.wraps(fn)
    def wrapper(*a, **k):
        try:
            return fn(*a, **k)
        except PermissionError as e:
            return str(e)
    return wrapper


@_scope_guard
def status() -> str:
    if not themes.available():
        return (
            "Shopify not connected. Add SHOPIFY_STORE and SHOPIFY_ADMIN_TOKEN to .env, "
            "and make sure the custom app has read_themes + write_themes scopes."
        )
    live = themes.live_theme()
    draft = themes.draft_theme()
    lines = [f"Live theme: {live['name']} (id {live['id']})" if live else "Live theme: none found?"]
    if draft:
        lines.append(f"Draft theme: {draft['name']} (id {draft['id']}) — edits go here")
        lines.append(f"Preview: {themes.preview_url(draft['id'])}")
    else:
        lines.append(
            "Draft theme: NONE — edits would hit the LIVE site directly.\n"
            "Strongly recommended: in Shopify admin, Online Store -> Themes -> (...) -> "
            "Duplicate your live theme and rename it to include 'draft' or 'agent'. "
            "Takes 30 seconds and protects your live store."
        )
    return "\n".join(lines)


@_scope_guard
def edit(instruction: str, asset_key: str = "") -> str:
    if not themes.available():
        return status()
    if not instruction.strip():
        return "Describe the change you want, e.g. 'make the countdown timer larger on mobile'."

    theme, is_draft = themes.working_theme()
    if not theme:
        return "No theme found on the store."
    tid = theme["id"]

    warning = ""
    if not is_draft:
        warning = (
            "\n\n⚠ NO DRAFT THEME FOUND — this edit was applied to your LIVE theme. "
            "A backup was saved first (use `site rollback` to undo). Duplicate your theme "
            "in Shopify admin to enable safe drafts."
        )

    # 1) Pick the file(s) if not specified
    if not asset_key:
        assets = themes.list_assets(tid)
        editable = [a for a in assets if a.split(".")[-1] in ("liquid", "json", "css", "scss", "js")]
        pick = llm.ask_json(
            "Which ONE theme file should be edited for this change request?\n"
            f"REQUEST: {instruction}\n\n"
            f"AVAILABLE FILES:\n{json.dumps(editable)}\n\n"
            'Respond as JSON: {"key": "<exact file key>", "why": "<one line>"}\n'
            "Prefer sections/ and templates/ files for layout/content changes, "
            "assets/*.css for pure styling, config/settings_data.json only for "
            "theme-setting toggles.",
            system="You are a Shopify Impulse theme expert.",
            max_tokens=300,
        )
        asset_key = pick.get("key", "")
        if asset_key not in editable:
            return f"Couldn't confidently pick a file for that request. Try naming one (e.g. sections/drop-hero.liquid). Candidate was: {pick}"

    # 2) Read, 3) rewrite
    original = themes.read_asset(tid, asset_key)
    if not original:
        return f"File {asset_key} is empty or unreadable."
    if len(original) > 60000:
        return f"{asset_key} is too large ({len(original)} chars) for a safe automated rewrite. Edit it in the Shopify code editor, or point me at a smaller file."

    new_content = llm.ask(
        f"Rewrite this Shopify theme file to implement the change.\n\n"
        f"CHANGE REQUEST: {instruction}\n\n"
        f"FILE: {asset_key}\n"
        f"CURRENT CONTENT:\n{original}\n\n"
        "Rules: return the COMPLETE new file content and NOTHING else — no fences, no "
        "commentary. Preserve all existing functionality, schema blocks, and Liquid "
        "logic that the change doesn't touch. Match the existing code style. "
        "Keep the brand aesthetic: #08090b ink, #9fb3bf steel accent, minimal.",
        system="You are a senior Shopify theme developer. Output only file content.",
        max_tokens=8000,
    ).strip()
    # Strip accidental fences
    if new_content.startswith("```"):
        new_content = new_content.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    # Sanity floor: refuse suspicious shrinkage (likely truncation)
    if len(new_content) < len(original) * 0.4 and "delete" not in instruction.lower() and "remove" not in instruction.lower():
        return (
            f"Aborted: rewrite came back {len(new_content)} chars vs original "
            f"{len(original)} — looks truncated. Nothing was written. Try a more "
            "specific instruction or a smaller file."
        )

    # 4) Backup + write
    themes.write_asset(tid, asset_key, new_content)

    # 5) Summarize + preview
    summary = llm.ask(
        f"In 3-5 bullet-free sentences, summarize what changed between these two versions "
        f"of {asset_key} for the store owner. Be specific about visual/behavioral effects.\n\n"
        f"BEFORE (truncated):\n{original[:4000]}\n\nAFTER (truncated):\n{new_content[:4000]}",
        max_tokens=400,
    )
    target = "draft theme" if is_draft else "LIVE theme"
    return (
        f"## Edit applied to {asset_key} ({target})\n\n{summary}\n\n"
        f"**Preview:** {themes.preview_url(tid)}\n"
        f"(open while logged into Shopify admin; live site is "
        f"{'untouched until you publish' if is_draft else 'ALREADY updated'})\n\n"
        f"Undo anytime: `python agent.py site rollback --file {asset_key}`"
        + warning
    )


@_scope_guard
def ideas() -> str:
    if not themes.available():
        return status()
    theme, is_draft = themes.working_theme()
    tid = theme["id"]
    file_dump = []
    for key in IDEA_FILES:
        try:
            content = themes.read_asset(tid, key)
            if content:
                file_dump.append(f"=== {key} ===\n{content[:8000]}")
        except Exception:
            continue
    asset_list = themes.list_assets(tid)

    return llm.ask(
        "Review my Shopify storefront code and give improvement ideas.\n\n"
        f"THEME FILES:\n\n{chr(10).join(file_dump) if file_dump else '(files unreadable)'}\n\n"
        f"ALL FILES IN THEME:\n{json.dumps(asset_list)[:3000]}\n\n"
        "Give me:\n"
        "1. TOP 5 SITE IMPROVEMENTS ranked by conversion impact for a single-product "
        "drop store — each with: what, why it matters for conversion, and the exact "
        "instruction I could give my agent's site editor to implement it.\n"
        "2. MOBILE CHECK — anything in the code that likely breaks or underwhelms on "
        "phones (where most traffic lands from IG/TikTok).\n"
        "3. SPEED — anything in these files adding load time.\n"
        "4. ONE BOLD IDEA — a distinctive site feature that expresses martial arts × "
        "streetwear that competitors' templated stores can't match.\n"
        "Ground every point in the actual code above — no generic CRO listicles.",
        system="You are a senior Shopify CRO consultant and theme developer.",
        max_tokens=4000,
    )


@_scope_guard
def publish_draft(confirm: bool = False) -> str:
    if not themes.available():
        return status()
    draft = themes.draft_theme()
    if not draft:
        return "No draft theme to publish."
    if not confirm:
        return (
            f"This will make '{draft['name']}' your LIVE site.\n"
            "Run: python agent.py site publish --yes  (or confirm in the Command Center)"
        )
    return themes.publish(draft["id"])


def rollback_file(asset_key: str) -> str:
    if not themes.available():
        return status()
    theme, _ = themes.working_theme()
    return themes.rollback(theme["id"], asset_key)
