"""Opportunity scanner: surfaces brand ideas and gaps Jordan might be missing.

Scans across seven lenses:
  product     — new SKUs, variants, bundles, accessories
  content     — untapped formats, series, storytelling angles
  channels    — platforms/tactics not being used (TikTok, Pinterest, email content, SEO)
  community   — audience-building mechanics (UGC, challenges, ambassador seeds)
  retention   — post-purchase, LTV, repeat-buy mechanics
  positioning — brand-story angles, collab archetypes, cultural moments
  ops         — packaging, unboxing, margin, pricing plays

Grounds itself in whatever real data is connected (funnel mix, competitors,
Shopify) so ideas fit the brand's actual stage, not generic startup advice.
"""
import json

import llm
from connectors import posts as posts_src, shopify
from modules import competitors as comp_mod
from modules import funnel

LENSES = ["product", "content", "channels", "community", "retention", "positioning", "ops"]


def scan(lens: str = "ALL", count: int = 3) -> str:
    lens = lens.lower()
    context_parts = []

    # Ground in real data where available
    posts = posts_src.fetch_all()
    if posts:
        try:
            tagged = funnel.classify_posts(posts)
            mix = {}
            hooks = set()
            for p in tagged:
                mix[p["stage"]] = mix.get(p["stage"], 0) + 1
                if p.get("hook_type"):
                    hooks.add(p["hook_type"])
            context_parts.append(
                f"CURRENT CONTENT: funnel mix {mix}, hook types already used: {sorted(hooks)}"
            )
        except Exception:
            context_parts.append(f"CURRENT CONTENT: {len(posts)} recent posts (unclassified)")

    logged = comp_mod.load_logged_posts()
    if logged:
        context_parts.append(
            "COMPETITOR LANDSCAPE (observed): "
            + "; ".join(f"{p.get('brand')}: {p.get('post_description')}" for p in logged[:15])
        )

    if shopify.available():
        try:
            snap = shopify.store_snapshot()
            context_parts.append("STORE SNAPSHOT:\n" + json.dumps(snap, default=str)[:4000])
        except Exception as e:
            context_parts.append(f"STORE: error fetching ({e})")

    context_parts.append(
        "KNOWN ROADMAP (do NOT re-suggest these as new ideas): fist/palm silhouette "
        "the brand's hero product, its product system, influencer collabs, "
        "thermal long sleeves."
    )

    if lens == "all":
        lens_instruction = (
            f"Scan ALL seven lenses: {', '.join(LENSES)}. "
            f"Give the {count} strongest ideas PER lens."
        )
    elif lens in LENSES:
        lens_instruction = f"Deep-dive the '{lens}' lens only. Give {max(count, 5)} ideas."
    else:
        return f"Unknown lens '{lens}'. Use one of: {', '.join(LENSES)}, or ALL."

    return llm.ask(
        "Identify opportunities and ideas I might be missing for my brand.\n\n"
        + "\n\n".join(context_parts)
        + f"\n\n{lens_instruction}\n\n"
        "Rules:\n"
        "- Every idea must fit a solo founder with limited budget — flag anything that "
        "requires capital or a team as 'later stage'.\n"
        "- For each idea: name it, one-line pitch, why it advances the brand's stated vision of "
        "martial arts into streetwear specifically (kill it if it doesn't), effort level (S/M/L), "
        "expected payoff, and the literal first step to test it this week.\n"
        "- Include at least one contrarian idea per lens — something most streetwear "
        "brands do that this brand should deliberately NOT do, or an unusual move.\n"
        "- End with a TOP 3 across all ideas ranked by (fit × payoff ÷ effort), "
        "and note which ONE to test before/around the July 30 drop window.\n"
        "- Do not suggest anything requiring licensed IP (Bruce Lee likeness, film "
        "stills) — original interpretations of martial arts culture only.",
        system=(
            "You are a brand strategist who has scaled multiple small DTC streetwear/"
            "jewelry brands past $1M. You spot non-obvious moves, not listicle advice."
        ),
        max_tokens=4000,
    )
