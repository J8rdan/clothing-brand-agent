"""First-run setup: asks a few questions and writes data/brand.txt.

Designed for people who have never edited a config file. Nothing here touches
API keys — those live in .env and have their own guide.
"""
import shutil
from pathlib import Path

import config

BRAND_FILE = config.DATA_DIR / "brand.txt"
EXAMPLE = Path(__file__).parent.parent / "brand.example.txt"

QUESTIONS = [
    ("name", "What's your brand called?", "e.g. Nova Supply"),
    ("website", "What's your website? (press Enter to skip)", "e.g. yourbrand.com"),
    ("sells", "In one line, what do you sell?", "e.g. minimal streetwear basics"),
    ("vision", "What does your brand stand for? (this guides every recommendation)",
     "e.g. make technical outerwear people actually wear daily"),
    ("look", "Describe your look — colours, photography, packaging",
     "e.g. clean white backgrounds, natural light, flat-lay product shots"),
    ("hero", "What's your main/hero product, and what makes it different?",
     "e.g. our signature pendant — steel, premium vs competitors"),
    ("audience", "Who buys from you?", "e.g. 18-30, streetwear and design-led shoppers"),
    ("channels", "Which channels do you use?",
     "e.g. Instagram @yourhandle, TikTok, Klaviyo email, Shopify, Meta ads"),
    ("works", "Anything that's worked well so far? (press Enter to skip)",
     "e.g. influencer collabs, reels beat static posts"),
]


def run() -> str:
    print()
    print("=" * 60)
    print("  CB AGENT — BRAND SETUP")
    print("=" * 60)
    print()
    print("I'll ask a few questions about your brand. The agent uses your")
    print("answers for every piece of advice it gives you.")
    print()
    print("Answer in plain English. Press Enter to skip anything optional.")
    print("Nothing here is sent anywhere — it's saved on your computer.")
    print()

    if BRAND_FILE.exists():
        print(f"You already have a brand profile at:\n  {BRAND_FILE}")
        again = input("Replace it? (y/N): ").strip().lower()
        if again != "y":
            return "Kept your existing brand profile. Nothing changed."
        print()

    answers = {}
    for i, (key, question, hint) in enumerate(QUESTIONS, 1):
        print(f"[{i}/{len(QUESTIONS)}] {question}")
        print(f"      ({hint})")
        answers[key] = input("      > ").strip()
        print()

    if not answers.get("name"):
        return "No brand name given — setup cancelled. Run it again when you're ready."

    parts = [f"Brand: {answers['name']}"]
    if answers.get("website"):
        parts[0] += f" ({answers['website']})"
    if answers.get("sells"):
        parts[0] += f" — {answers['sells']}"
    if answers.get("vision"):
        parts.append(f"\nVISION: {answers['vision']}\nThis vision is the lens for every "
                     "recommendation. Ideas that don't deepen this identity or grow the "
                     "brand's reach are noise.")
    if answers.get("look"):
        parts.append(f"\nVisual identity: {answers['look']}")
    if answers.get("hero"):
        parts.append(f"\nHero product: {answers['hero']}")
    if answers.get("audience"):
        parts.append(f"\nAudience: {answers['audience']}")
    if answers.get("channels"):
        parts.append(f"\nChannels: {answers['channels']}")
    if answers.get("works"):
        parts.append(f"\nWhat has worked so far: {answers['works']}")

    profile = "\n".join(parts).strip() + "\n"
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    BRAND_FILE.write_text(profile, encoding="utf-8")

    out = [
        "",
        "=" * 60,
        "  SAVED",
        "=" * 60,
        "",
        f"Your brand profile is saved at:\n  {BRAND_FILE}",
        "",
        "You can edit that file any time in Notepad to refine it.",
        "",
        "NEXT STEP: add your API keys so the agent can think and pull data.",
        '  Double-click "3 - API KEY GUIDE.bat" for the walkthrough,',
        "  then run:  python agent.py doctor",
        "",
    ]
    return "\n".join(out)


def ensure_brand_file():
    """Copy the example into data/ on first run so the file is discoverable."""
    target = config.DATA_DIR / "brand.txt"
    if not target.exists() and EXAMPLE.exists():
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy(EXAMPLE, target)
