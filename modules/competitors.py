"""Competitor creative engine.

The IG API doesn't allow pulling other accounts' analytics, so this works from
manual observation — which is honestly better data anyway (you see what the
algorithm pushes). Log competitor posts you notice performing well into
data/competitors.csv:

    brand,post_description,format,hook,views_or_likes,why_it_worked,url

Then `python agent.py competitors` will analyze patterns and generate
on-brand adaptations. It can also work from just a list of brand names
(data/competitor_brands.txt, one per line) using the LLM's knowledge of
common winning formats in the niche.
"""
import csv

import config
import llm

COMPETITORS_CSV = config.DATA_DIR / "competitors.csv"
BRANDS_TXT = config.DATA_DIR / "competitor_brands.txt"


def load_logged_posts() -> list[dict]:
    if not COMPETITORS_CSV.exists():
        return []
    with open(COMPETITORS_CSV, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


FIELDNAMES = ["brand", "post_description", "format", "hook",
              "views_or_likes", "why_it_worked", "url"]


def log_post(row: dict) -> str:
    """Append one competitor post to the CSV, creating it with a header if needed.
    Missing fields are filled blank; unknown fields are ignored. Deduplicates on url."""
    clean = {k: str(row.get(k, "") or "").replace("\n", " ").strip() for k in FIELDNAMES}

    # skip exact-duplicate URLs so re-analyzing the same video doesn't double-log
    if clean["url"]:
        for existing in load_logged_posts():
            if existing.get("url", "").strip() == clean["url"]:
                return f"Already logged: {clean['brand'] or clean['url']}"

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    new_file = not COMPETITORS_CSV.exists()
    with open(COMPETITORS_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if new_file:
            w.writeheader()
        w.writerow(clean)
    n = len(load_logged_posts())
    return f"Logged {clean['brand'] or 'post'} to competitors.csv ({n} total)."


def load_brand_list() -> list[str]:
    if not BRANDS_TXT.exists():
        return []
    return [l.strip() for l in BRANDS_TXT.read_text(encoding="utf-8").splitlines() if l.strip()]


def recommend() -> str:
    posts = load_logged_posts()
    brands = load_brand_list()

    if not posts and not brands:
        return (
            f"No competitor data yet. Create either:\n"
            f"  {COMPETITORS_CSV}  (columns: brand,post_description,format,hook,"
            f"views_or_likes,why_it_worked,url)\n"
            f"  {BRANDS_TXT}  (one brand name per line)\n"
            "Tip: spend 15 min in your IG explore feed, log 10 posts from dark/minimal "
            "streetwear or jewelry brands that clearly performed — that's enough."
        )

    prompt_parts = []
    if posts:
        prompt_parts.append("LOGGED COMPETITOR POSTS (observed performing well):")
        for p in posts:
            prompt_parts.append(
                f"- {p.get('brand')}: {p.get('post_description')} | format: {p.get('format')} "
                f"| hook: {p.get('hook')} | perf: {p.get('views_or_likes')} "
                f"| why: {p.get('why_it_worked')}"
            )
    if brands:
        prompt_parts.append("\nCOMPETITOR/ADJACENT BRANDS TO DRAW PATTERNS FROM:")
        prompt_parts.append(", ".join(brands))

    prompt_parts.append(
        "\nTasks:\n"
        "1. PATTERN ANALYSIS — what creative patterns are winning in this niche right now "
        "(hooks, formats, pacing, audio use, caption style)? Ground it in the logged posts "
        "where available.\n"
        "2. FUNNEL MAP — tag each pattern TOF/MOF/BOF.\n"
        "3. ADAPTATIONS FOR US — 10 concrete post concepts adapting these patterns to "
        "the brand's aesthetic and hero product described above. For each: funnel stage, format, "
        "exact hook line, shot description (I shoot on a Sony A7 II with bounce flash, "
        "the studio setup and collaborators noted in the brand profile), "
        "caption draft, and CTA.\n"
        "4. Rank the 10 by expected impact for a small account building reach.\n"
        "Never copy a competitor's exact creative — adapt the mechanism, not the content."
    )

    return llm.ask(
        "\n".join(prompt_parts),
        system="You are a short-form content strategist for dark-aesthetic streetwear brands.",
        max_tokens=4000,
    )
