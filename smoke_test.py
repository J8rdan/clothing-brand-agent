"""Full-system smoke test: exercises every module and GUI endpoint with mocked
LLM + network. Any exception is a failure. Run: python3 smoke_test.py"""
import json
import sys
import threading
import time
import traceback
import urllib.request
from unittest.mock import patch

sys.path.insert(0, ".")

FAILURES = []


def check(name, fn):
    try:
        fn()
        print(f"  OK   {name}")
    except Exception as e:
        FAILURES.append((name, e))
        print(f"  FAIL {name}: {e}")
        traceback.print_exc(limit=3)


def fake_ask(prompt, system="", max_tokens=3000, model=""):
    return "Mocked analysis output."


def fake_ask_json(prompt, system="", max_tokens=3000, model=""):
    if "Classify these posts" in prompt:
        n = prompt.count('"i":')
        return [{"i": i, "stage": ["TOF", "MOF", "BOF"][i % 3], "hook_type": "curiosity",
                 "cta": "soft", "rationale": "r"} for i in range(n)]
    if "video ideas" in prompt:
        return [{"title": f"Test idea {i} {time.time_ns()}", "hook": "h", "format": "reel",
                 "stage": "TOF", "pillar": "craft", "effort": "S"} for i in range(25)]
    if "theme file" in prompt:
        return {"key": "sections/drop-hero.liquid", "why": "w"}
    return [{"i": 0, "stage": "TOF", "hook_type": "x", "cta": "none", "rationale": "r"}]


FAKE_ADS = [{"ad_id": "1", "ad_name": "A", "campaign_name": "C", "spend": "10", "impressions": "1000",
             "clicks": "50", "ctr": "5.0", "cpc": "0.2", "frequency": "1.2",
             "actions": [{"action_type": "complete_registration", "value": "8"}]}]


def run_all():
    llm_patches = [
        patch("llm.ask", fake_ask),
        patch("llm.ask_json", fake_ask_json),
        patch("llm.chat", lambda messages, system="": "Mocked chat reply."),
    ]
    for p in llm_patches:
        p.start()

    # Modules also import llm directly; patch their references
    import modules.funnel, modules.competitors, modules.advisor, modules.content
    import modules.opportunities, modules.daily_report, modules.weekly, modules.debrief
    import modules.videos, modules.ads, modules.subagents, modules.video
    for m in (modules.funnel, modules.competitors, modules.advisor, modules.content,
              modules.opportunities, modules.daily_report, modules.weekly, modules.debrief,
              modules.videos, modules.ads, modules.subagents):
        m.llm.ask = fake_ask
        m.llm.ask_json = fake_ask_json

    from modules import (funnel, competitors, advisor, content, opportunities,
                         daily_report, weekly, debrief, videos, site, ads)
    import tokens as tok

    check("funnel.funnel_report (CSV mode)", lambda: funnel.funnel_report())
    check("competitors.recommend (empty state)", lambda: competitors.recommend())
    check("advisor.advise", lambda: advisor.advise())
    check("advisor.advise --focus", lambda: advisor.advise(focus="PDP"))
    check("content.generate all stages", lambda: [content.generate(stage=s) for s in ("TOF", "MOF", "BOF", "ALL")])
    check("opportunities.scan ALL", lambda: opportunities.scan())
    check("opportunities.scan single lens", lambda: opportunities.scan(lens="retention"))
    check("opportunities.scan bad lens returns msg", lambda: opportunities.scan(lens="bogus"))
    check("daily_report.generate", lambda: daily_report.generate(save=True))
    check("daily_report day2 (reads previous)", lambda: daily_report.generate(save=True))
    check("weekly.generate", lambda: weekly.generate(save=True))
    check("videos.generate 25", lambda: videos.generate(count=25, save=True))
    check("videos dedupe day2", lambda: videos.generate(count=25, save=False))
    check("debrief no-shopify no-tty", lambda: debrief.generate(save=False))
    check("ads.report (not connected msg)", lambda: ads.report())
    with patch("connectors.meta_ads.available", lambda: True), \
         patch("connectors.meta_ads.ad_insights", lambda days=7: FAKE_ADS), \
         patch("connectors.meta_ads.ad_cta_types", lambda: {"1": "SIGN_UP"}):
        check("ads.report (connected)", lambda: ads.report())
        check("ads.compact_summary", lambda: ads.compact_summary())
    check("site.status (not connected msg)", lambda: site.status())
    check("site.edit (not connected msg)", lambda: site.edit("x"))
    from modules import subagents
    check("subagents.list_agents", lambda: subagents.list_agents())
    check("subagents.available", lambda: subagents.available())
    check("subagents.run content-marketer", lambda: subagents.run("content-marketer", "test task"))
    check("subagents.run unknown name", lambda: subagents.run("nope", "t"))
    from modules import video as _video
    check("video.analyze empty source", lambda: _video.analyze(""))
    check("video.analyze missing binaries msg", lambda: _video_missing(_video))
    check("video._parse_watch_output", lambda: _video.analyze.__self__ if False else _parse_check(_video))
    check("subagents.run multi-agent-coordinator", lambda: subagents.run("multi-agent-coordinator", "test task"))
    check("subagents survive an unreadable file", lambda: _bad_file_check(subagents))
    check("tokens.ensure_fresh (empty store)", lambda: tok.ensure_fresh())
    check("tokens.auth_status", lambda: tok.auth_status())

    # GUI endpoints
    import gui
    threading.Thread(target=lambda: gui.app.run(port=8390), daemon=True).start()
    time.sleep(1.2)

    def get(p):
        return urllib.request.urlopen(f"http://127.0.0.1:8390{p}", timeout=10).read().decode()

    def post(p, body):
        req = urllib.request.Request(f"http://127.0.0.1:8390{p}", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        return json.loads(urllib.request.urlopen(req, timeout=10).read())

    def run_gui_cmd(command, args=None):
        job = post("/api/run", {"command": command, "args": args or {}})["job"]
        for _ in range(40):
            time.sleep(0.4)
            j = json.loads(get(f"/api/job/{job}"))
            if j["status"] != "running":
                if j["status"] == "error":
                    raise RuntimeError(j["output"])
                return j["output"]
        raise TimeoutError(command)

    check("GUI /", lambda: get("/"))
    check("GUI /api/status", lambda: get("/api/status"))
    check("GUI /api/reports", lambda: get("/api/reports"))
    check("GUI /api/agents", lambda: json.loads(get("/api/agents")))
    check("GUI session isolation", lambda: _session_isolation_check("http://127.0.0.1:8390"))
    for cmd, args in [("report", {}), ("weekly", {}), ("funnel", {}), ("competitors", {}),
                      ("advise", {"focus": "x"}), ("content", {"stage": "TOF", "count": 2}),
                      ("ideas", {"lens": "ops"}), ("videos", {"count": 25}),
                      ("debrief", {"date": "2026-07-30", "days": 3}),
                      ("ads", {"days": 7}), ("agents", {}),
                      ("watch", {"source": ""}),
                      ("run_agent", {"name": "content-marketer", "task": "t"}),
]:
        check(f"GUI run {cmd}", lambda c=cmd, a=args: run_gui_cmd(c, a))
    check("GUI chat", lambda: run_gui_cmd_chat(post, get))

    # Report file endpoints (daily/weekly/videos/debrief mapping)
    files = json.loads(get("/api/reports"))
    kinds = {f["kind"] for f in files}
    check("GUI reports include daily+weekly+videos",
          lambda: (_ for _ in ()).throw(AssertionError(kinds)) if not {"daily", "weekly", "videos"} <= kinds else None)
    for f in files[:6]:
        check(f"GUI open report {f['kind']}/{f['name']}",
              lambda f=f: json.loads(get(f"/api/report/{f['kind']}/{f['path'].split('/')[1]}"))["content"])


def _competitor_log_check():
    """log_post appends, dedupes on url, and survives a fresh file."""
    import tempfile, shutil
    from pathlib import Path
    import config
    from modules import competitors
    orig = competitors.COMPETITORS_CSV
    d = Path(tempfile.mkdtemp())
    competitors.COMPETITORS_CSV = d / "competitors.csv"
    try:
        competitors.log_post({"brand": "A", "url": "http://x/1", "hook": "h"})
        competitors.log_post({"brand": "A", "url": "http://x/1"})   # dup
        competitors.log_post({"brand": "B", "url": "http://x/2"})
        rows = competitors.load_logged_posts()
        assert len(rows) == 2, rows
        assert set(rows[0].keys()) >= set(competitors.FIELDNAMES)
    finally:
        competitors.COMPETITORS_CSV = orig
        shutil.rmtree(d, ignore_errors=True)


def _video_missing(video):
    """When binaries are absent, analyze() returns an install message, not a crash."""
    orig = video.shutil.which
    video.shutil.which = lambda b: None
    try:
        r = video.analyze("https://example.com/x.mp4")
        assert "PATH" in r or "install" in r.lower(), r
    finally:
        video.shutil.which = orig


def _parse_check(video):
    sample = ("## Frames\n\n- `/tmp/x/frame_0001.jpg` (t=00:00, reason=uniform)\n"
              "\n## Transcript\n\n```\nhello world\n```\n---\n")
    fp, tr, hd = video._parse_watch_output(sample)
    assert fp == ["/tmp/x/frame_0001.jpg"], fp
    assert tr == "hello world", tr


def _session_isolation_check(base):
    """A job started under one session must not be readable by another."""
    import urllib.request, json as _json
    def post(path, payload, sid):
        req = urllib.request.Request(
            base + path, data=_json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", "X-CB-Session": sid})
        return _json.loads(urllib.request.urlopen(req).read())
    def get(path, sid):
        req = urllib.request.Request(base + path, headers={"X-CB-Session": sid})
        return urllib.request.urlopen(req).read().decode()
    job = post("/api/run", {"command": "funnel", "args": {}}, "sessX")["job"]
    # a different session must NOT read it: expect an HTTP 404
    import urllib.error
    try:
        get("/api/job/" + job, "sessY")
        raise AssertionError("cross-session job read succeeded — isolation broken")
    except urllib.error.HTTPError as e:
        assert e.code == 404, f"expected 404 cross-session, got {e.code}"
    own = _json.loads(get("/api/job/" + job, "sessX"))
    assert own["status"] in ("running", "done", "error"), own


def _bad_file_check(subagents):
    """A non-utf8 agent file must not break listing (regression guard)."""
    p = subagents.AGENTS_DIR / "_smoke_bad.md"
    p.write_bytes(b"---\nname: bad\n---\nbody \xff\xfe")
    try:
        names = {a["name"] for a in subagents.available()}
        assert "content-marketer" in names, names
    finally:
        p.unlink()


def run_gui_cmd_chat(post, get):
    import gui
    job = post("/api/chat", {"message": "hi"})["job"]
    for _ in range(40):
        time.sleep(0.4)
        j = json.loads(get(f"/api/job/{job}"))
        if j["status"] != "running":
            if j["status"] == "error":
                raise RuntimeError(j["output"])
            return
    raise TimeoutError("chat")


if __name__ == "__main__":
    run_all()
    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILURES:")
        for name, e in FAILURES:
            print(f"  - {name}: {e}")
        sys.exit(1)
    print("ALL CHECKS PASSED")
