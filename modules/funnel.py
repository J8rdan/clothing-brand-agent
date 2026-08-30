"""Funnel classifier: tags content TOF / MOF / BOF and analyzes your funnel mix.

TOF (top of funnel)    = reach & discovery: trends, entertainment, philosophy, lifestyle
MOF (middle of funnel) = consideration: product education, behind-the-scenes, craft, styling
BOF (bottom of funnel) = conversion: drops, offers, urgency, social proof, direct CTA
"""
import json

import config
import llm
from connectors import instagram, posts as posts_src

CLASSIFY_SYSTEM = """You are a DTC content strategist for a streetwear/jewelry brand.
Classify each Instagram post into exactly one funnel stage:
- TOF: discovery/reach content — entertainment, philosophy, trends, lifestyle, no hard sell
- MOF: consideration content — product education, craft/BTS, styling, brand story
- BOF: conversion content — drop announcements, urgency, price/offer, direct buy CTA, testimonials

For each post also identify: hook_type (e.g. curiosity, motion, statement, trend-audio),
cta (none/soft/hard), and a one-line rationale."""


def classify_posts(posts: list[dict]) -> list[dict]:
    if not posts:
        return []
    compact = [
        {
            "i": i,
            "caption": (p.get("caption") or "")[:400],
            "media_type": p.get("media_type", ""),
            "platform": p.get("platform", "instagram"),
        }
        for i, p in enumerate(posts)
    ]
    result = llm.ask_json(
        "Classify these posts. Return a JSON array of objects with keys: "
        "i, stage (TOF|MOF|BOF), hook_type, cta, rationale.\n\n"
        + json.dumps(compact, ensure_ascii=False),
        system=CLASSIFY_SYSTEM,
        max_tokens=4000,
    )
    by_index = {r["i"]: r for r in result if isinstance(r, dict) and "i" in r}
    out = []
    for i, p in enumerate(posts):
        tag = by_index.get(i, {})
        out.append({**p, "stage": tag.get("stage", "?"), "hook_type": tag.get("hook_type", ""),
                    "cta": tag.get("cta", ""), "rationale": tag.get("rationale", "")})
    return out


def funnel_report() -> str:
    posts = posts_src.fetch_all()
    if not posts:
        return (
            "No posts found. Set IG_ACCESS_TOKEN + IG_BUSINESS_ID and/or "
            "TIKTOK_ACCESS_TOKEN in .env, or fill the CSVs:\n"
            f"  {instagram.MY_POSTS_CSV} (caption,media_type,likes,comments,saves,"
            "shares,reach,views,posted_at,url)\n"
            "  data/my_tiktoks.csv (caption,views,likes,comments,shares,saves,posted_at,url)"
        )
    tagged = classify_posts(posts)

    # Deterministic mix + engagement stats per stage
    stats = {s: {"count": 0, "reach": 0, "saves": 0, "shares": 0, "likes": 0, "comments": 0}
             for s in ("TOF", "MOF", "BOF", "?")}
    for p in tagged:
        s = stats[p["stage"] if p["stage"] in stats else "?"]
        s["count"] += 1
        for k in ("reach", "saves", "shares", "likes", "comments"):
            s[k] += p.get(k, 0)

    lines = ["FUNNEL MIX", "=" * 40]
    total = len(tagged)
    for stage in ("TOF", "MOF", "BOF"):
        s = stats[stage]
        pct = 100 * s["count"] / total if total else 0
        avg_reach = s["reach"] / s["count"] if s["count"] else 0
        lines.append(
            f"{stage}: {s['count']} posts ({pct:.0f}%) | avg reach {avg_reach:,.0f} | "
            f"saves {s['saves']} | shares {s['shares']}"
        )
    lines.append("")
    lines.append("PER-POST TAGS")
    lines.append("=" * 40)
    for p in tagged:
        cap = (p.get("caption") or "(no caption)").replace("\n", " ")[:60]
        plat = (p.get("platform", "ig") or "ig")[:2].upper()
        lines.append(f"[{p['stage']}|{plat}] {cap}  — hook: {p['hook_type']}, cta: {p['cta']}")

    # LLM strategic read on the mix
    analysis = llm.ask(
        "Here is my current Instagram funnel mix and per-stage engagement:\n"
        + "\n".join(lines)
        + "\n\nGive me: 1) what's wrong or missing in this mix for a brand at my stage "
        "(pre/early drops, small following, building pixel data), 2) the ideal TOF/MOF/BOF "
        "ratio for the next 30 days, 3) three specific post ideas per under-served stage. "
        "Be direct and specific to this brand.",
        system="You are a blunt, practical DTC growth strategist.",
    )
    return "\n".join(lines) + "\n\nSTRATEGIC READ\n" + "=" * 40 + "\n" + analysis
