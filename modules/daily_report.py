"""Daily report: one briefing covering content, funnel, ads, competitors, and store.

Saves each report to data/reports/YYYY-MM-DD.md and includes yesterday's report
in the prompt when available, so the agent tracks day-over-day change and
doesn't repeat itself.
"""
import datetime
import json

import config
import llm
from connectors import klaviyo, meta_ads, posts as posts_src, shopify
from modules import competitors as comp_mod
from modules import funnel

REPORTS_DIR = config.DATA_DIR / "reports"


def _previous_report() -> str:
    REPORTS_DIR.mkdir(exist_ok=True)
    reports = sorted(REPORTS_DIR.glob("*.md"))
    if not reports:
        return ""
    return reports[-1].read_text(encoding="utf-8")[:4000]


def generate(save: bool = True) -> str:
    today = datetime.date.today().isoformat()
    sections = []

    # --- Content + funnel ---
    posts = posts_src.fetch_all()
    if posts:
        try:
            tagged = funnel.classify_posts(posts)
            mix, stage_engagement = {}, {}
            for p in tagged:
                st = p["stage"]
                mix[st] = mix.get(st, 0) + 1
                e = stage_engagement.setdefault(st, {"reach": 0, "saves": 0, "shares": 0})
                e["reach"] += p.get("reach", 0)
                e["saves"] += p.get("saves", 0)
                e["shares"] += p.get("shares", 0)
            top = sorted(tagged, key=lambda p: p.get("reach", 0) + p.get("views", 0), reverse=True)[:3]
            sections.append(
                "CONTENT & FUNNEL:\n"
                f"Posts analyzed: {len(tagged)} | Mix: {mix}\n"
                f"Per-stage engagement: {stage_engagement}\n"
                "Top posts by reach/views:\n"
                + "\n".join(
                    f"  [{p['stage']}|{p.get('platform', 'ig')}] {(p.get('caption') or '')[:70]} — reach {p.get('reach', 0):,}, views {p.get('views', 0):,}, "
                    f"saves {p.get('saves', 0)}, hook: {p.get('hook_type', '')}"
                    for p in top
                )
            )
        except Exception as e:
            sections.append(f"CONTENT & FUNNEL: classification failed ({e}); "
                            f"{len(posts)} posts pulled.")
    else:
        sections.append("CONTENT & FUNNEL: no post data (connect IG/TikTok APIs or fill data/my_posts.csv / data/my_tiktoks.csv).")

    # --- Ads ---
    if meta_ads.available():
        try:
            from modules import ads as ads_mod
            summary = ads_mod.compact_summary(days=7)
            sections.append(summary or "ADS: connected, no delivery in last 7d.")
        except Exception as e:
            sections.append(f"ADS: fetch error ({e})")
    else:
        sections.append("ADS: Meta API not connected.")

    # --- Competitors ---
    logged = comp_mod.load_logged_posts()
    if logged:
        sections.append(
            "COMPETITOR LOG:\n"
            + "\n".join(
                f"  {p.get('brand')}: {p.get('post_description')} ({p.get('format')}, "
                f"{p.get('views_or_likes')})"
                for p in logged[-10:]
            )
        )
    else:
        sections.append("COMPETITOR LOG: empty (data/competitors.csv).")

    # --- Store ---
    if shopify.available():
        try:
            snap = shopify.store_snapshot()
            sections.append(
                f"STORE: {snap.get('recent_orders_count', '?')} recent orders | "
                f"{len(snap.get('products', []))} products"
            )
        except Exception as e:
            sections.append(f"STORE: fetch error ({e})")
    else:
        sections.append("STORE: Shopify API not connected.")

    # --- List (daily snapshot keeps weekly history accurate) ---
    if klaviyo.available():
        try:
            ks = klaviyo.stats(days=1)
            sections.append(
                f"LIST: {ks['total']:,} total | joined last 24h: {ks['new']} "
                f"(email {ks['email']}, sms {ks['sms']})"
            )
        except Exception as e:
            sections.append(f"LIST: Klaviyo fetch error ({e})")
    else:
        sections.append("LIST: Klaviyo not connected.")

    prev = _previous_report()
    prev_block = f"\n\nYESTERDAY'S REPORT (for day-over-day comparison):\n{prev}" if prev else ""

    brief = llm.ask(
        f"Write my daily brand brief for {today}.\n\nRAW DATA:\n\n"
        + "\n\n".join(sections)
        + prev_block
        + "\n\nFormat the brief as:\n"
        "1. HEADLINE — the single most important thing today, one sentence.\n"
        "2. WHAT CHANGED — day-over-day movement (or 'first report' if no history).\n"
        "3. CONTENT — funnel mix status, what's working, what to post TODAY (one specific "
        "concept with hook).\n"
        "4. ADS — status and any action needed (skip detail if not connected).\n"
        "5. COMPETITORS — any pattern worth reacting to (skip if log empty).\n"
        "6. TODAY'S TOP 3 ACTIONS — specific, doable by a solo founder in one day, ordered.\n"
        "7. WATCH — one metric or risk to keep an eye on.\n"
        "Keep it tight — this is a 2-minute morning read, not an essay. "
        "Flag missing data sources once, briefly, at the end.",
        system="You are the brand's chief of staff writing the founder's morning brief.",
        max_tokens=2500,
    )

    if save:
        REPORTS_DIR.mkdir(exist_ok=True)
        out = REPORTS_DIR / f"{today}.md"
        out.write_text(brief, encoding="utf-8")
        brief += f"\n\n[saved to {out}]"
    return brief
