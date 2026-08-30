"""Content generator: produces funnel-targeted post concepts on demand."""
import llm


def generate(stage: str = "ALL", count: int = 5, topic: str = "") -> str:
    stage = stage.upper()
    stage_brief = {
        "TOF": "TOF (discovery/reach): philosophy, motion, trend adaptation, lifestyle — no selling",
        "MOF": "MOF (consideration): craft, BTS, styling, brand story, product education",
        "BOF": "BOF (conversion): drop urgency, offer framing, social proof, direct CTA",
        "ALL": "a balanced mix across TOF, MOF, and BOF",
    }.get(stage, "a balanced mix across TOF, MOF, and BOF")

    topic_line = f"\nTheme/occasion to build around: {topic}" if topic else ""

    return llm.ask(
        f"Generate {count} Instagram post concepts targeting {stage_brief}.{topic_line}\n\n"
        "My production reality: Sony A7 II + Tamron 28-75 f/2.8, Godox bounce flash, "
        "the equipment and collaborators described in the brand profile for "
        "on-model shots. Solo founder — concepts must be shootable in one session.\n\n"
        "For each concept give: funnel stage, format (reel/carousel/static/story), "
        "exact hook (first line or first 1.5 seconds), shot-by-shot description with "
        "camera settings where relevant, caption draft in the brand's voice, "
        "CTA, and audio suggestion type (don't name specific copyrighted tracks — "
        "describe the vibe/genre to search for).",
        system="You are the brand's in-house creative director. Work from the brand profile provided.",
        max_tokens=4000,
    )
