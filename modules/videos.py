"""Video idea engine: generates 100+ video ideas per day, never repeating itself.

Every idea it has ever generated is logged (data/video_ideas/idea_log.jsonl).
Each new batch is told what's already been produced, so day 30 is as fresh as
day 1. Ideas rotate through 8 content pillars and are tagged TOF/MOF/BOF.

Output: data/video_ideas/YYYY-MM-DD.md — the full 100, plus a TOP 10 shortlist
of what's most worth shooting today.
"""
import datetime
import json

import config
import llm

VIDEOS_DIR = config.DATA_DIR / "video_ideas"
LOG_FILE = VIDEOS_DIR / "idea_log.jsonl"

PILLARS = [
    "training & discipline (martial arts movement, drills, physicality)",
    "product & craft (pendant macro, metal, packaging, making-of)",
    "philosophy & mindset (martial arts wisdom as text/voiceover pieces)",
    "street style (on-model, outfit builds, how it's worn)",
    "unboxing & drop culture (packaging, orders, restocks, scarcity)",
    "collab & UGC (creators, customers, duets, reactions)",
    "trend adaptation (current reel/TikTok formats bent to the brand)",
    "story & world-building (the brand's vision, behind the founder)",
]

BATCH_SIZE = 25


def _recent_titles(limit: int = 400) -> list[str]:
    if not LOG_FILE.exists():
        return []
    lines = LOG_FILE.read_text(encoding="utf-8").strip().splitlines()
    titles = []
    for line in lines[-limit:]:
        try:
            titles.append(json.loads(line)["title"])
        except (json.JSONDecodeError, KeyError):
            continue
    return titles


def _log(ideas: list[dict]):
    VIDEOS_DIR.mkdir(exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        for i in ideas:
            f.write(json.dumps({"title": i.get("title", ""), "date": datetime.date.today().isoformat()}) + "\n")


def generate(count: int = 100, save: bool = True) -> str:
    today = datetime.date.today().isoformat()
    avoid = _recent_titles()
    all_ideas: list[dict] = []
    seen = {t.lower() for t in avoid}

    batches = max(1, -(-count // BATCH_SIZE))  # ceil
    for b in range(batches):
        # Rotate pillar emphasis so batches don't converge
        emphasis = PILLARS[b % len(PILLARS)] + " and " + PILLARS[(b + 3) % len(PILLARS)]
        avoid_slice = (avoid + [i["title"] for i in all_ideas])[-250:]
        try:
            batch = llm.ask_json(
                f"Generate {BATCH_SIZE} short-form video ideas (Reels/TikTok) for the brand.\n"
                f"Emphasize these pillars this batch: {emphasis} — but include a spread.\n\n"
                f"DO NOT repeat or closely resemble any of these existing ideas:\n"
                f"{json.dumps(avoid_slice)}\n\n"
                'Return a JSON array. Each item: {"title": "<6-10 word idea name>", '
                '"hook": "<the exact first line or first 1.5s visual>", '
                '"format": "<reel|tiktok|carousel-video|story>", '
                '"stage": "<TOF|MOF|BOF>", "pillar": "<short pillar name>", '
                '"effort": "<S|M|L>"}\n'
                "Constraints: shootable by a solo founder (Sony A7 II, ZV-E10, bounce "
                "flash, basement lightbox, occasional collaborator for on-model). "
                "Roughly 60% TOF, 25% MOF, 15% BOF. Every idea must serve the vision of "
                "bringing martial arts into streetwear — kill generic jewelry content.",
                system="You are a short-form video strategist for a martial-arts streetwear brand.",
                max_tokens=4000,
            )
        except Exception as e:
            if not all_ideas:
                return f"Idea generation failed: {e}"
            break
        for i in batch if isinstance(batch, list) else []:
            t = (i.get("title") or "").strip()
            if t and t.lower() not in seen:
                seen.add(t.lower())
                all_ideas.append(i)
        if len(all_ideas) >= count:
            break
    all_ideas = all_ideas[:count] if len(all_ideas) > count else all_ideas

    # Build the markdown doc
    by_stage = {"TOF": [], "MOF": [], "BOF": []}
    for i in all_ideas:
        by_stage.setdefault(i.get("stage", "TOF"), by_stage["TOF"]).append(i)

    doc = [f"# {len(all_ideas)} video ideas — {today}\n"]
    for stage in ("TOF", "MOF", "BOF"):
        items = by_stage.get(stage, [])
        if not items:
            continue
        doc.append(f"\n## {stage} ({len(items)})\n")
        for n, i in enumerate(items, 1):
            doc.append(
                f"{n}. **{i.get('title','')}** [{i.get('pillar','')}, {i.get('format','reel')}, "
                f"effort {i.get('effort','S')}]  \n   Hook: {i.get('hook','')}"
            )

    # Daily shortlist
    shortlist = llm.ask(
        f"From this list of {len(all_ideas)} video ideas, pick the TOP 10 most worth "
        "shooting in the current moment (drop window, small account building reach, "
        "solo founder time constraints). For each: the title, why now, and what single "
        "shot makes or breaks it.\n\n"
        + json.dumps([{"title": i.get("title"), "hook": i.get("hook"), "stage": i.get("stage"),
                       "effort": i.get("effort")} for i in all_ideas]),
        system="You are the brand's creative director. Ruthless prioritizer.",
        max_tokens=1500,
    )
    doc.insert(1, f"\n## TODAY'S TOP 10\n\n{shortlist}\n\n---\n")

    result = "\n".join(doc)
    _log(all_ideas)
    if save:
        VIDEOS_DIR.mkdir(exist_ok=True)
        out = VIDEOS_DIR / f"{today}.md"
        out.write_text(result, encoding="utf-8")
        result += f"\n\n[saved to {out}]"
    return result
