"""Drop debrief: reconciles a drop's results into numbers + a playbook.

Usage: python agent.py debrief --date 2026-07-30 [--days 3]

Deterministic metrics first (never hallucinated), then an LLM read:
  - Orders, revenue, AOV, units in the drop window (Shopify)
  - Waitlist conversion: orders / list size at drop (Klaviyo)
  - Revenue per subscriber
  - Ad spend + revenue/spend in window (Meta, if connected)
  - Content in window by funnel stage

Falls back to manual entry: if Shopify isn't connected it asks for the
topline numbers interactively, so the debrief works regardless.
Saves to data/debriefs/<date>.md
"""
import datetime
import json

import config
import llm
from connectors import klaviyo, meta_ads, posts as posts_src, shopify
from modules import funnel

DEBRIEFS_DIR = config.DATA_DIR / "debriefs"


def _shopify_window(start: datetime.date, days: int) -> dict | None:
    if not shopify.available():
        return None
    end = start + datetime.timedelta(days=days)
    try:
        data = shopify._get(
            "orders.json",
            {
                "status": "any",
                "created_at_min": f"{start.isoformat()}T00:00:00Z",
                "created_at_max": f"{end.isoformat()}T00:00:00Z",
                "limit": 250,
                "fields": "total_price,created_at,line_items,customer,referring_site",
            },
        ).get("orders", [])
    except Exception:
        return None
    revenue = sum(float(o.get("total_price") or 0) for o in data)
    units = sum(
        int(li.get("quantity") or 0) for o in data for li in (o.get("line_items") or [])
    )
    return {
        "orders": len(data),
        "revenue": round(revenue, 2),
        "units": units,
        "aov": round(revenue / len(data), 2) if data else 0,
    }


def _manual_numbers() -> dict:
    import sys
    if not sys.stdin.isatty():
        return {"orders": 0, "revenue": 0, "units": 0, "aov": 0,
                "note": "Shopify not connected and no terminal for manual entry — "
                        "connect Shopify or run `python agent.py debrief` in a terminal "
                        "to type the numbers in."}
    print("Shopify not connected — enter drop numbers manually (blank = 0):")

    def ask_num(label):
        try:
            return float(input(f"  {label}: ").strip() or 0)
        except ValueError:
            return 0.0

    orders = int(ask_num("Total orders"))
    revenue = ask_num("Total revenue")
    units = int(ask_num("Units sold"))
    return {
        "orders": orders,
        "revenue": revenue,
        "units": units,
        "aov": round(revenue / orders, 2) if orders else 0,
    }


def generate(drop_date: str = "2026-07-30", days: int = 3, save: bool = True) -> str:
    start = datetime.date.fromisoformat(drop_date)
    metrics: dict = {"drop_date": drop_date, "window_days": days}

    sales = _shopify_window(start, days) or _manual_numbers()
    metrics.update(sales)

    # Waitlist conversion
    if klaviyo.available():
        try:
            total_list = klaviyo.total_count()
            metrics["list_size"] = total_list
            if total_list:
                metrics["waitlist_conversion_pct"] = round(100 * sales["orders"] / total_list, 2)
                metrics["revenue_per_subscriber"] = round(sales["revenue"] / total_list, 2)
        except Exception as e:
            metrics["klaviyo_error"] = str(e)

    # Ad spend in window
    if meta_ads.available():
        try:
            insights = meta_ads.campaign_insights(days=7)
            spend = sum(float(c.get("spend") or 0) for c in insights)
            metrics["ad_spend_7d"] = round(spend, 2)
            if spend:
                metrics["revenue_per_ad_dollar"] = round(sales["revenue"] / spend, 2)
        except Exception as e:
            metrics["ads_error"] = str(e)

    # Content in the run-up + drop window
    content_summary = ""
    posts = posts_src.fetch_all()
    if posts:
        try:
            tagged = funnel.classify_posts(posts)
            mix = {}
            for p in tagged:
                mix[p["stage"]] = mix.get(p["stage"], 0) + 1
            top = sorted(tagged, key=lambda p: p.get("reach", 0) + p.get("views", 0), reverse=True)[:5]
            content_summary = (
                f"Funnel mix around the drop: {mix}\nTop content:\n"
                + "\n".join(
                    f"  [{p['stage']}|{p.get('platform', 'ig')}] "
                    f"{(p.get('caption') or '')[:60]} — reach {p.get('reach', 0):,}, "
                    f"views {p.get('views', 0):,}"
                    for p in top
                )
            )
        except Exception:
            content_summary = f"{len(posts)} posts in window (unclassified)."

    header = (
        f"# Drop Debrief — {drop_date} (+{days}d window)\n\n"
        "## The numbers\n```\n" + json.dumps(metrics, indent=2) + "\n```\n"
    )

    narrative = llm.ask(
        "Write the debrief analysis for my product drop.\n\n"
        f"METRICS (exact, do not restate incorrectly):\n{json.dumps(metrics, indent=2)}\n\n"
        f"CONTENT:\n{content_summary or 'no content data'}\n\n"
        "Sections:\n"
        "1. VERDICT — one honest sentence: how did this drop actually go for a brand at "
        "this stage? Calibrate against realistic small-brand benchmarks (waitlist->purchase "
        "for warm SMS/email lists typically lands ~1-10%; be honest about where we sit).\n"
        "2. WHAT WORKED — tie results to specific inputs (content stages, list, ads) where "
        "the data supports it; say 'unclear' where it doesn't.\n"
        "3. WHAT LEAKED — where buyers were likely lost (list->site, site->cart, cart->buy). "
        "Flag what data is missing to know for sure and how to capture it next time.\n"
        "4. NEXT DROP PLAYBOOK — the 5 most important changes for drop #2, ordered, each "
        "tied to something learned here.\n"
        "5. THIS WEEK — 3 post-drop actions (e.g. post-purchase flow, UGC ask to buyers, "
        "restock/waitlist decision).\n"
        "No cheerleading, no doom — a coach reviewing game tape.",
        system="You are a DTC operator who has run dozens of drops. Honest, benchmark-aware.",
        max_tokens=3000,
    )

    result = header + "\n" + narrative
    if save:
        DEBRIEFS_DIR.mkdir(exist_ok=True)
        out = DEBRIEFS_DIR / f"{drop_date}.md"
        out.write_text(result, encoding="utf-8")
        result += f"\n\n[saved to {out}]"
    return result
