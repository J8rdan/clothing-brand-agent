"""Ads module: per-ad performance report with scale / watch / kill calls.

Deterministic layer first (numbers are computed, never guessed):
  - Per ad: spend, CTR, CPC, CTA button type, results, cost per result
  - "Result" auto-detects the deepest meaningful action available:
    purchase > lead/complete_registration > link_click
  - Ranked best -> worst by cost per result (CTR breaks ties)
  - Ads with spend under the significance floor are flagged low-data, not judged

Then the LLM turns the table into budget moves: which ads to put more into,
which to watch, which to kill — with reasoning tied to the numbers.
"""
import json

import llm
from connectors import meta_ads

MIN_SPEND = 3.0  # below this, verdicts are noise

# (action_type, label, tier) — lower tier = more valuable result
RESULT_PRIORITY = [
    ("purchase", "purchases", 0),
    ("omni_purchase", "purchases", 0),
    ("lead", "leads", 1),
    ("complete_registration", "signups", 1),
    ("link_click", "link clicks", 2),
]


def _extract_result(actions: list[dict]) -> tuple[int, str, int]:
    """Returns (count, label, tier) — tier 0 is the most valuable result type."""
    amap = {a.get("action_type"): float(a.get("value") or 0) for a in (actions or [])}
    for key, label, tier in RESULT_PRIORITY:
        if amap.get(key):
            return int(amap[key]), label, tier
    return 0, "none", 99


def build_table(days: int = 7) -> list[dict]:
    raw = meta_ads.ad_insights(days=days)
    ctas = meta_ads.ad_cta_types()
    rows = []
    for a in raw:
        spend = float(a.get("spend") or 0)
        results, result_type, result_tier = _extract_result(a.get("actions"))
        rows.append(
            {
                "ad": a.get("ad_name", "?"),
                "campaign": a.get("campaign_name", "?"),
                "cta_button": ctas.get(a.get("ad_id"), "?"),
                "spend": round(spend, 2),
                "impressions": int(a.get("impressions") or 0),
                "clicks": int(a.get("clicks") or 0),
                "ctr_pct": round(float(a.get("ctr") or 0), 2),
                "cpc": round(float(a.get("cpc") or 0), 2),
                "frequency": round(float(a.get("frequency") or 0), 1),
                "results": results,
                "result_type": result_type,
                "cost_per_result": round(spend / results, 2) if results else None,
                "result_tier": result_tier,
                "low_data": spend < MIN_SPEND,
            }
        )
    # Best -> worst. Result VALUE outranks result cost: an ad producing signups
    # beats an ad producing only link clicks, regardless of cost-per-result —
    # comparing $/click to $/subscriber would reward the shallowest ads.
    # Within the same result tier, cheaper cost-per-result wins; CTR breaks ties.
    def sort_key(r):
        if r["low_data"]:
            return (2, 0, 0, 0)
        if r["cost_per_result"] is None:
            return (1, 0, 0, -r["ctr_pct"])
        return (0, r["result_tier"], r["cost_per_result"], -r["ctr_pct"])

    rows.sort(key=sort_key)
    return rows


def report(days: int = 7) -> str:
    if not meta_ads.available():
        return (
            "Meta ads not connected. Add META_AD_ACCOUNT_ID to .env (and run "
            "`python agent.py auth meta` for the token) to enable ad analysis."
        )
    try:
        rows = build_table(days=days)
    except Exception as e:
        return f"Ad insights fetch failed: {e}"
    if not rows:
        return f"No ads with delivery in the last {days} days."

    lines = [f"## Ad performance — last {days} days (best → worst)\n"]
    for i, r in enumerate(rows, 1):
        cpr = f"${r['cost_per_result']}" if r["cost_per_result"] is not None else "—"
        flag = "  ⚠ low spend, not judged" if r["low_data"] else ""
        lines.append(
            f"{i}. **{r['ad']}** ({r['campaign']}) — CTA: {r['cta_button']}  \n"
            f"   spend ${r['spend']} | CTR {r['ctr_pct']}% | CPC ${r['cpc']} | "
            f"{r['results']} {r['result_type']} @ {cpr} | freq {r['frequency']}{flag}"
        )
    table = "\n".join(lines)

    analysis = llm.ask(
        f"Here is my per-ad Meta performance table (already ranked best to worst, "
        f"numbers are exact):\n\n{json.dumps(rows, indent=1)}\n\n"
        "My context: small account, early pixel maturity, the metric that matters most "
        "is cost per SMS/email subscriber and (post-drop) cost per purchase — not raw CPC.\n\n"
        "Give me:\n"
        "1. SCALE — which ad(s) to put more budget into, how much more (e.g. +20-30%/day, "
        "never doubling at once), and why the numbers support it.\n"
        "2. WATCH — ads that are promising but need more data or a specific fix "
        "(e.g. good CTR but weak results = landing page problem, not ad problem; "
        "frequency >3 = fatigue incoming).\n"
        "3. KILL — the worst performer(s) and what the numbers say went wrong "
        "(hook? CTA button mismatch? audience?).\n"
        "4. CTA READ — does the CTA button type correlate with performance here? "
        "Any test worth running?\n"
        "5. ONE TEST for next week — a single new ad variant to launch based on what "
        "the winners share.\n"
        "Only judge ads with meaningful spend; say 'needs data' for the low-spend ones. "
        "Be decisive — I want budget moves, not observations.",
        system="You are a Meta ads media buyer for small DTC brands. Decisive, numbers-first.",
        max_tokens=2500,
    )
    return table + "\n\n## Budget moves\n\n" + analysis


def compact_summary(days: int = 7) -> str:
    """One-paragraph version for the daily report."""
    if not meta_ads.available():
        return ""
    try:
        rows = build_table(days=days)
    except Exception:
        return ""
    if not rows:
        return ""
    judged = [r for r in rows if not r["low_data"]]
    if not judged:
        return f"ADS: {len(rows)} ads live, all under ${MIN_SPEND} spend — too early to judge."
    best, worst = judged[0], judged[-1]
    total_spend = round(sum(r["spend"] for r in rows), 2)
    return (
        f"ADS (last {days}d): ${total_spend} across {len(rows)} ads. "
        f"Best: '{best['ad']}' (CTA {best['cta_button']}, CTR {best['ctr_pct']}%, "
        f"{best['results']} {best['result_type']} @ ${best['cost_per_result']}). "
        f"Worst: '{worst['ad']}' (CTR {worst['ctr_pct']}%, "
        f"cost/result {'$' + str(worst['cost_per_result']) if worst['cost_per_result'] else 'no results'})."
    )
