"""Video analysis.

Wraps the bundled `watch` pipeline (skills_watch/scripts/watch.py) which downloads
a video via yt-dlp, extracts frames with ffmpeg, and pulls a transcript. This module
runs it, reads the extracted frames back, and sends frames + transcript to Claude so
it can actually analyze what's on screen — framed around your brand's content strategy.

Requires the `yt-dlp` and `ffmpeg` binaries on PATH. If they're missing, this returns
a clear install message instead of a stack trace.

Note on scope: analyzing videos you don't own (competitor/inspo content) is for private
study, not redistribution. Downloaded files are deleted after analysis by default.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

import config
import llm

SCRIPTS = Path(__file__).parent.parent / "skills_watch" / "scripts"
WATCH = SCRIPTS / "watch.py"

# Detail presets map to the watch script's own flags; keep the frame budget modest
# so a single analysis doesn't blow the API's image limit or the token budget.
DETAIL_PRESETS = {
    "quick": ["--detail", "efficient", "--max-frames", "12"],
    "standard": ["--detail", "balanced", "--max-frames", "24"],
    "deep": ["--detail", "balanced", "--max-frames", "36"],
    "transcript": ["--detail", "transcript"],
}

ANALYSIS_SYSTEM = """You are the brand's content analyst. You are shown frames sampled \
from a video (each tagged with its timestamp) plus a transcript. Analyze what is \
actually on screen and said — not guesses.

Structure your analysis for the brand described in the brand profile:
1. HOOK (first 3 seconds) — what happens visually and audibly, and whether it would \
stop a scroll. Be specific about the opening frame.
2. STRUCTURE & PACING — how the video is built, where attention is held or lost.
3. WHAT WORKS — techniques worth adapting.
4. FOR YOUR BRAND — concrete, adaptable takeaways for the brand's own content. Never suggest \
copying; suggest what principle to borrow.

Be concrete and reference specific timestamps. If frames or transcript are missing, \
say so rather than inventing detail."""


def _which_missing() -> list[str]:
    return [b for b in ("yt-dlp", "ffmpeg", "ffprobe") if shutil.which(b) is None]


def available() -> bool:
    return WATCH.exists() and not _which_missing()


def _py() -> str:
    """The interpreter to launch the watch script with — same one running us."""
    return sys.executable or "python3"


def _parse_watch_output(text: str) -> tuple[list[str], str, str]:
    """Pull frame paths, transcript, and the report header out of watch.py stdout."""
    frame_paths = re.findall(r"^- `([^`]+\.(?:jpg|jpeg|png))`", text, flags=re.MULTILINE)
    transcript = ""
    m = re.search(r"## Transcript\s*\n(.*?)(?:\n---|\Z)", text, flags=re.DOTALL)
    if m:
        block = m.group(1)
        fenced = re.search(r"```\s*\n(.*?)```", block, flags=re.DOTALL)
        transcript = fenced.group(1).strip() if fenced else ""
    header = text.split("## Frames")[0].strip()
    return frame_paths, transcript, header


EXTRACT_SYSTEM = """From the video analysis you just produced, extract competitor log fields as JSON with EXACTLY these keys: brand, post_description, format, hook, views_or_likes, why_it_worked. Rules:
- brand: the creator/brand if identifiable from the video or URL, else "".
- format: one of Reel, Short, TikTok, Carousel, Video, or "" if unclear.
- hook: the opening line or first-frame concept, one short phrase.
- views_or_likes: only if actually stated on screen or in the transcript, else "".
- why_it_worked: one sentence, the single biggest reason it performed.
Return ONLY the JSON object, no prose."""


def _autolog(source: str, analysis: str) -> str:
    """Extract structured fields from the analysis and append to competitors.csv."""
    try:
        from modules import competitors
        fields = llm.ask_json(
            f"URL/source: {source}\n\nANALYSIS:\n{analysis[:3500]}",
            system=EXTRACT_SYSTEM, max_tokens=500,
        )
        if not isinstance(fields, dict):
            return ""
        fields["url"] = source if source.startswith("http") else ""
        return competitors.log_post(fields)
    except Exception:
        return ""   # logging is best-effort; never break the analysis over it


def analyze(source: str, question: str = "", detail: str = "standard", log: bool = True) -> str:
    """Download/extract a video and analyze it. `source` is a URL or local path.
    When `log` is True and the source is a URL, the result is also appended to
    competitors.csv so your competitor dataset builds itself."""
    if not source.strip():
        return "Give me a video URL or file path to analyze."

    if not WATCH.exists():
        return "Video analysis scripts are missing from skills_watch/scripts/."

    missing = _which_missing()
    if missing:
        return (
            "Video analysis needs these tools installed and on your PATH:\n  "
            + ", ".join(missing)
            + "\n\nWindows install (one time):\n"
            "  1. yt-dlp:  pip install yt-dlp\n"
            "  2. ffmpeg:  download from https://www.gyan.dev/ffmpeg/builds/ \n"
            "     (get the 'release full' build), unzip, and add its \\bin folder to PATH.\n"
            "Then restart your terminal and try again."
        )

    # Instagram actively blocks automated downloads. Warn before spending time on it.
    src_l = source.lower()
    is_instagram = "instagram.com" in src_l or "instagr.am" in src_l

    flags = DETAIL_PRESETS.get(detail, DETAIL_PRESETS["standard"])
    cmd = [_py(), str(WATCH), source, *flags]

    try:
        # watch.py prints the report to stdout, progress to stderr.
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=600,
            cwd=str(SCRIPTS),
        )
    except subprocess.TimeoutExpired:
        return "The video took too long to process (over 10 minutes). Try a shorter clip or a specific range."
    except Exception as exc:  # noqa: BLE001
        return f"Could not run the video pipeline: {exc}"

    if proc.returncode != 0:
        err = (proc.stderr or "").strip()
        tail = "\n".join(err.splitlines()[-6:])
        if is_instagram:
            return (
                "Instagram blocked this download.\n\n"
                "Instagram actively prevents automated access, so most Instagram links "
                "can't be analyzed this way. YouTube, TikTok, Vimeo and Loom links work "
                "reliably.\n\n"
                "What you can do instead:\n"
                "  - Save/download the reel to your phone, move it to your computer, "
                "then paste the FILE PATH here instead of the link\n"
                "  - Or describe the video in the chat bar and ask for a breakdown\n\n"
                f"Technical detail:\n{tail[:300] or 'download failed'}"
            )
        return f"Video processing failed:\n{tail or 'unknown error'}"

    frame_paths, transcript, header = _parse_watch_output(proc.stdout)

    # Locate the working dir so we can clean it up afterward.
    work_dir = None
    wm = re.search(r"_Work dir: `([^`]+)`", proc.stdout)
    if wm:
        work_dir = Path(wm.group(1))

    try:
        if not frame_paths and not transcript:
            return (
                "The pipeline ran but produced neither frames nor a transcript.\n\n"
                + header
            )

        q = question.strip() or "Analyze this video for our content strategy."
        prompt_parts = [f"QUESTION: {q}", "", header]
        if transcript:
            prompt_parts += ["", "TRANSCRIPT:", transcript[:6000]]
        if frame_paths:
            prompt_parts += ["", f"{len(frame_paths)} frames follow, in chronological order."]
        prompt = "\n".join(prompt_parts)

        if frame_paths:
            existing = [p for p in frame_paths if Path(p).exists()]
            analysis = llm.ask_with_images(
                prompt, existing, system=ANALYSIS_SYSTEM, max_tokens=4000
            )
        else:
            # transcript-only path
            analysis = llm.ask(prompt, system=ANALYSIS_SYSTEM, max_tokens=3000)

        if log and source.strip().startswith("http"):
            logged = _autolog(source, analysis)
            if logged:
                analysis += f"\n\n---\n**Competitor log:** {logged}"
        return analysis
    finally:
        # Always remove the pipeline's own temp working dir (it lives under the
        # system temp dir, never the user's own file location).
        import tempfile
        tmp_root = Path(tempfile.gettempdir())
        if work_dir and work_dir.exists():
            try:
                work_dir.relative_to(tmp_root)   # only delete if under system temp
                shutil.rmtree(work_dir, ignore_errors=True)
            except ValueError:
                pass  # not under temp — a user-specified out dir; leave it
