"""Improvement advisor: audits site + marketing setup and outputs a ranked action list."""
import json

import llm
from connectors import meta_ads, posts as posts_src, shopify
from modules import funnel


def advise(focus: str = "") -> str:
    context_parts = []

    # Shopify store data (if connected)
    if shopify.available():
        snap = shopify.store_snapshot()
        context_parts.append("SHOPIFY SNAPSHOT:\n" + json.dumps(snap, default=str)[:6000])
    else:
        context_parts.append(
            "SHOPIFY: not connected. Known setup: Impulse theme, dark custom drop-hero "
            "section with countdown + Klaviyo waitlist, customized password page, "
            "the hero product and packaging described in the brand profile."
        )

    # Meta ads performance (if connected)
    if meta_ads.available():
        try:
            insights = meta_ads.campaign_insights()
            context_parts.append("META ADS LAST 30D:\n" + json.dumps(insights, default=str)[:4000])
        except Exception as e:
            context_parts.append(f"META ADS: error fetching ({e})")
    else:
        context_parts.append(
            "META ADS: not connected. Known history: SMS pre-drop traffic campaign ran; "
            "cold conversion paused due to thin pixel data; broad targeting preferred."
        )

    # Content funnel mix (quick, reuses classifier)
    posts = posts_src.fetch_all()
    if posts:
        tagged = funnel.classify_posts(posts)
        mix = {}
        for p in tagged:
            mix[p["stage"]] = mix.get(p["stage"], 0) + 1
        context_parts.append(f"CONTENT FUNNEL MIX (recent posts): {mix}")

    focus_line = f"\nUser wants the audit focused on: {focus}" if focus else ""

    return llm.ask(
        "Audit my brand's current state and give improvement recommendations.\n\n"
        + "\n\n".join(context_parts)
        + focus_line
        + "\n\nOutput:\n"
        "1. TOP 5 IMPROVEMENTS ranked by (impact × ease) — for each: what, why, exactly how, "
        "and expected effect. Cover site/PDP, content, email/SMS flows, and ads as relevant.\n"
        "2. QUICK WINS — anything fixable in under 30 minutes.\n"
        "3. ONE THING TO STOP DOING.\n"
        "Be specific to a solo founder pre/just-post drop. No generic advice like "
        "'post consistently' — every rec must be concrete enough to execute today.",
        system="You are a senior DTC/CRO consultant doing a paid audit. Direct, specific, no filler.",
        max_tokens=4000,
    )
