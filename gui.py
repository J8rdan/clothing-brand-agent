"""CB Agent Command Center — local web GUI for the growth agent.

Run: python agent.py gui   (opens http://127.0.0.1:8377 in your browser)

Everything runs locally; nothing is exposed beyond your machine.
"""
import threading
import uuid
import webbrowser

from flask import Flask, jsonify, request, send_from_directory
from pathlib import Path

import config
import tokens

app = Flask(__name__, static_folder=None)
JOBS: dict = {}                 # job_id -> {status, output, session}
CHAT_HISTORY: dict = {}         # session_id -> [ {role, content}, ... ]
GUI_DIR = Path(__file__).parent / "gui_static"


def _session_id() -> str:
    """Per-tab session id, sent by the browser as X-CB-Session.
    Falls back to a shared bucket for non-browser callers (e.g. curl)."""
    return request.headers.get("X-CB-Session", "") or "default"


def _run_job(job_id: str, fn, *args, **kwargs):
    try:
        JOBS[job_id]["output"] = fn(*args, **kwargs)
        JOBS[job_id]["status"] = "done"
    except Exception as e:
        JOBS[job_id]["output"] = f"Error: {e}"
        JOBS[job_id]["status"] = "error"


def _start(fn, *args, session: str = "default", **kwargs) -> str:
    job_id = uuid.uuid4().hex[:12]
    JOBS[job_id] = {"status": "running", "output": "", "session": session}
    threading.Thread(target=_run_job, args=(job_id, fn) + args, kwargs=kwargs, daemon=True).start()
    return job_id


@app.get("/")
def index():
    return send_from_directory(GUI_DIR, "index.html")


@app.get("/api/status")
def status():
    st = config.connector_status()
    from connectors import klaviyo, tiktok
    st["tiktok"] = tiktok.available()
    st["klaviyo"] = klaviyo.available()
    return jsonify(st)


@app.post("/api/run")
def run():
    body = request.get_json(force=True)
    cmd = body.get("command", "")
    args = body.get("args", {}) or {}

    def dispatch():
        if cmd == "report":
            from modules import daily_report
            return daily_report.generate()
        if cmd == "weekly":
            from modules import weekly
            return weekly.generate()
        if cmd == "debrief":
            from modules import debrief
            return debrief.generate(
                drop_date=args.get("date", "2026-07-30"),
                days=int(args.get("days", 3)),
            )
        if cmd == "ads":
            from modules import ads
            return ads.report(days=int(args.get("days", 7)))
        if cmd == "funnel":
            from modules import funnel
            return funnel.funnel_report()
        if cmd == "competitors":
            from modules import competitors
            return competitors.recommend()
        if cmd == "advise":
            from modules import advisor
            return advisor.advise(focus=args.get("focus", ""))
        if cmd == "content":
            from modules import content
            return content.generate(
                stage=args.get("stage", "ALL"),
                count=int(args.get("count", 5)),
                topic=args.get("topic", ""),
            )
        if cmd == "videos":
            from modules import videos
            return videos.generate(count=int(args.get("count", 100)))
        if cmd == "ideas":
            from modules import opportunities
            return opportunities.scan(lens=args.get("lens", "ALL"), count=int(args.get("count", 3)))
        if cmd == "watch":
            from modules import video
            return video.analyze(args.get("source", ""), args.get("question", ""),
                                 detail=args.get("detail", "standard"),
                                 log=bool(args.get("log", 1)))
        if cmd == "agents":
            from modules import subagents
            return subagents.list_agents()
        if cmd == "run_agent":
            from modules import subagents
            return subagents.run(args.get("name", ""), args.get("task", ""))
        return f"Unknown command: {cmd}"

    def dispatch_with_refresh():
        # token refresh talks to Meta over the network; keep it off the request
        # thread so a slow refresh can never block or time out /api/run
        try:
            tokens.ensure_fresh()
        except Exception:
            pass
        return dispatch()

    return jsonify({"job": _start(dispatch_with_refresh, session=_session_id())})


@app.post("/api/chat")
def chat():
    body = request.get_json(force=True)
    msg = (body.get("message") or "").strip()
    if not msg:
        return jsonify({"error": "empty message"}), 400
    sid = _session_id()
    hist = CHAT_HISTORY.setdefault(sid, [])
    hist.append({"role": "user", "content": msg})
    history = list(hist[-20:])

    def do_chat():
        import llm
        text = llm.chat(history, system="You are CB Agent's growth strategist. Concise, direct.")
        hist.append({"role": "assistant", "content": text})
        return text

    return jsonify({"job": _start(do_chat, session=sid)})


@app.get("/api/job/<job_id>")
def job(job_id):
    j = JOBS.get(job_id)
    if not j:
        return jsonify({"status": "unknown"}), 404
    if j.get("session", "default") != _session_id():
        return jsonify({"status": "unknown"}), 404   # not this tab's job
    return jsonify({"status": j["status"], "output": j["output"]})


@app.post("/api/reset")
def reset():
    CHAT_HISTORY.pop(_session_id(), None)
    return jsonify({"ok": True})


@app.get("/api/agents")
def agents_list():
    try:
        from modules import subagents
        out = []
        for a in subagents.available():
            model = subagents.MODEL_MAP.get(a["model"], a["model"]) or config.CLAUDE_MODEL
            out.append({
                "name": a["name"],
                "description": a["description"],
                "tools": a["tools"],
                "model": model,
            })
        return jsonify(out)
    except Exception:
        return jsonify([])


@app.get("/api/reports")
def reports():
    out = []
    for kind, d in (("daily", config.DATA_DIR / "reports"), ("weekly", config.DATA_DIR / "weekly"), ("debrief", config.DATA_DIR / "debriefs"), ("videos", config.DATA_DIR / "video_ideas")):
        if d.exists():
            for f in sorted(d.glob("*.md"), reverse=True)[:14]:
                out.append({"kind": kind, "name": f.stem, "path": f"{kind}/{f.name}"})
    return jsonify(out)


@app.get("/api/report/<kind>/<name>")
def report_file(kind, name):
    d = config.DATA_DIR / {"daily": "reports", "weekly": "weekly", "debrief": "debriefs", "videos": "video_ideas"}.get(kind, "reports")
    f = (d / name).resolve()
    if not str(f).startswith(str(d.resolve())) or not f.exists():
        return jsonify({"error": "not found"}), 404
    return jsonify({"content": f.read_text(encoding="utf-8")})


def _lan_ip() -> str:
    """Best-effort local network IP of this machine."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))   # no packets sent; just picks the route
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def launch(port: int = 8377, open_browser: bool = True, lan: bool = False):
    url = f"http://127.0.0.1:{port}"
    if lan:
        ip = _lan_ip()
        print("=" * 58)
        print("  PHONE ACCESS ENABLED (same Wi-Fi only)")
        print(f"  On your phone's browser, go to:  http://{ip}:{port}")
        print()
        print("  Anyone else on this Wi-Fi can reach it too, and there is")
        print("  no password. Use it on your home network, not public Wi-Fi.")
        print("=" * 58)
    print(f"CB Agent Command Center running at {url}  (Ctrl+C to stop)")
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    app.run(host="0.0.0.0" if lan else "127.0.0.1", port=port, debug=False)
