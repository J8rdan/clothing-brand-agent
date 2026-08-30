"""Weekly report: list growth first, then the week in review across all channels."""
import datetime
import json

import config
import llm
from connectors import klaviyo, meta_ads, posts as posts_src, shopify
from modules import funnel

WEEKLY_DIR = config.DATA_DIR / "weekly"


def generate(save: bool = True) -> str:
    today = datetime.date.today().isoformat()
    sections = []

    # --- Klaviyo list growth (the headline) ---
    if klaviyo.available():
        try:
            s = klaviyo.stats(days=7)
            growth_line = (
                f"KLAVIYO LIST GROWTH (last 7d):\n"
                f"  New subscribers: {s['new']}  (email: {s['email']}, sms: {s['sms']})\n"
                f"  Total list size: {s['total']:,}"
            )
            if "total_delta_vs_history" in s:
                growth_line += f"\n  Net change vs last week's snapshot: {s['total_delta_vs_history']:+d}"
            sections.append(growth_line)
        except Exception as e:
            sections.append(f"KLAVIYO: fetch error ({e}) — check KLAVIYO_PRIVATE_KEY.")
    else:
        sections.append(
            "KLAVIYO: not connected. Add KLAVIYO_PRIVATE_KEY to .env "
            "(Settings -> API keys -> private key, read-only Lists+Profiles scope)."
        )

    # --- Content week in review ---
    posts = posts_src.fetch_all()
    if posts:
        try:
            tagged = funnel.classify_posts(posts)
            mix = {}
            for p in tagged:
                mix[p["stage"]] = mix.get(p["stage"], 0) + 1
            top = sorted(tagged, key=lambda p: p.get("reach", 0) + p.get("views", 0), reverse=True)[:5]
            sections.append(
                f"CONTENT: {len(tagged)} recent posts | funnel mix {mix}\n"
                "Top performers:\n"
                + "\n".join(
                    f"  [{p['stage']}|{p.get('platform', 'ig')}] "
                    f"{(p.get('caption') or '')[:60]} — reach {p.get('reach', 0):,}, "
                    f"views {p.get('views', 0):,}, saves {p.get('saves', 0)}"
                    for p in top
                )
            )
        except Exception:
            sections.append(f"CONTENT: {len(posts)} posts pulled (classification failed).")
    else:
        sections.append("CONTENT: no post data.")

    # --- Ads + store ---
    if meta_ads.available():
        try:
            sections.append("ADS (7d):\n" + json.dumps(meta_ads.campaign_insights(days=7), default=str)[:2500])
        except Exception as e:
            sections.append(f"ADS: fetch error ({e})")
    if shopify.available():
        try:
            snap = shopify.store_snapshot()
            sections.append(f"STORE: {snap.get('recent_orders_count', '?')} recent orders")
        except Exception as e:
            sections.append(f"STORE: fetch error ({e})")

    # --- Previous weekly for comparison ---
    WEEKLY_DIR.mkdir(exist_ok=True)
    prior = sorted(WEEKLY_DIR.glob("*.md"))
    prev_block = f"\n\nLAST WEEK'S REPORT:\n{prior[-1].read_text(encoding='utf-8')[:3000]}" if prior else ""

    brief = llm.ask(
        f"Write my weekly review for the week ending {today}.\n\nRAW DATA:\n\n"
        + "\n\n".join(sections)
        + prev_block
        + "\n\nFormat:\n"
        "1. LIST GROWTH — lead with subscriber numbers: how many joined this week "
        "(email vs SMS split), total size, and pace vs last week. This is the #1 metric.\n"
        "2. WEEK IN REVIEW — content and funnel performance, what worked.\n"
        "3. SUBSCRIBER QUALITY — anything notable (e.g. SMS vs email ratio shifting, "
        "growth vs content cadence correlation).\n"
        "4. NEXT WEEK'S PLAN — 3 priorities, with one specifically aimed at list growth.\n"
        "5. TREND WATCH — one thing to monitor.\n"
        "Concise — a 3-minute Sunday read.",
        system="You are the brand's chief of staff writing the founder's weekly review.",
        max_tokens=2500,
    )

    if save:
        out = WEEKLY_DIR / f"{today}.md"
        out.write_text(brief, encoding="utf-8")
        brief += f"\n\n[saved to {out}]"
    return brief
