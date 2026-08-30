#!/usr/bin/env python3
"""CB Agent — growth automation for clothing brands — standalone CLI.

Commands:
  doctor                      Check which connectors are configured
  funnel                      Classify your content TOF/MOF/BOF + strategic read
  ads [--days 7|30]           Per-ad report: CTR, CTA, scale/watch/kill budget moves
  competitors                 Analyze competitor creatives + generate adaptations
  advise [--focus TEXT]       Site/marketing audit with ranked improvements
  content [--stage TOF|MOF|BOF|ALL] [--count N] [--topic TEXT]
                              Generate funnel-targeted post concepts
  report [--no-save]           Daily brief: content, funnel, ads, competitors, store
  weekly [--no-save]           Weekly review: Klaviyo list growth + week in review
  debrief [--date YYYY-MM-DD] [--days N]
                              Post-drop reconciliation + next-drop playbook
  videos [--count N]           Generate 100+ video ideas (never repeats past days)
  ideas [--lens LENS] [--count N]
                              Scan for brand opportunities you might be missing
                              (lenses: product, content, channels, community,
                               retention, positioning, ops, ALL)
  setup                       Set up your brand profile (run this first)
  agents                      List installed subagents (agents/*.md)
  run-agent NAME "task"       Run a subagent on a task
  watch URL/path "question"   Analyze a video (frames + transcript) for content strategy
  chat                        Free-form strategy chat with full brand context
  auth status|meta|tiktok     Token setup and auto-refresh management
  gui [--port N] [--lan]      Launch the Command Center (--lan = reachable from your phone)
  site ideas                  Site improvement ideas grounded in your theme code
  site edit "instruction" [--file KEY]
                              AI-edit the theme (draft-first, auto-backup)
  site publish [--yes]        Publish the draft theme to live
  site rollback --file KEY    Restore a file from its latest backup
"""
import argparse
import sys

import config


def cmd_doctor(_):
    if not config.brand_is_configured():
        print("!" * 62)
        print("BRAND PROFILE NOT SET UP")
        print("  Run:  python agent.py setup")
        print("  (or edit data/brand.txt)")
        print("  Without it, the agent doesn't know who your brand is.")
        print("!" * 62)
        print()
    if config.ENV_WARNING:
        print("!" * 62)
        print("PROBLEM: " + config.ENV_WARNING)
        print("!" * 62)
        print()
    status = config.connector_status()
    icons = {True: "OK ", False: "-- "}
    print("CONNECTOR STATUS")
    print(f"  {icons[status['anthropic']]}Anthropic API  (required)")
    print(f"  {icons[status['instagram']]}Instagram Graph API  (falls back to data/my_posts.csv)")
    print(f"  {icons[status['meta_ads']]}Meta Marketing API  (optional)")
    print(f"  {icons[status['tiktok']]}TikTok Display API  (falls back to data/my_tiktoks.csv)")
    print(f"  {icons[status['klaviyo']]}Klaviyo API  (list growth tracking)")
    print(f"  {icons[status['shopify']]}Shopify Admin API  (optional)")
    if not status["anthropic"]:
        print("\nAdd ANTHROPIC_API_KEY to .env to enable AI features.")
    if not any(status.values()) and not config.ENV_WARNING:
        print("\nNothing is connected. Check that your .env file is named exactly")
        print('".env" (not ".env.txt") and sits in this folder:')
        print(f"  {config.ENV_PATH.parent}")
    print(f"\nData dir: {config.DATA_DIR}")


def cmd_ads(args):
    from modules import ads
    print(ads.report(days=args.days))


def cmd_funnel(_):
    from modules import funnel
    print(funnel.funnel_report())


def cmd_competitors(_):
    from modules import competitors
    print(competitors.recommend())


def cmd_advise(args):
    from modules import advisor
    print(advisor.advise(focus=args.focus or ""))


def cmd_content(args):
    from modules import content
    print(content.generate(stage=args.stage, count=args.count, topic=args.topic or ""))


def cmd_report(args):
    from modules import daily_report
    print(daily_report.generate(save=not args.no_save))


def cmd_debrief(args):
    from modules import debrief
    print(debrief.generate(drop_date=args.date, days=args.days))


def cmd_weekly(args):
    from modules import weekly
    print(weekly.generate(save=not args.no_save))


def cmd_videos(args):
    from modules import videos
    print(videos.generate(count=args.count))


def cmd_ideas(args):
    from modules import opportunities
    print(opportunities.scan(lens=args.lens, count=args.count))



def cmd_gui(args):
    import gui
    gui.launch(port=args.port, lan=args.lan)


def cmd_auth(args):
    import tokens
    if args.action == "doctor":
        print(tokens.token_doctor())
    else:
        {"status": tokens.auth_status, "meta": tokens.auth_meta,
         "tiktok": tokens.auth_tiktok}[args.action]()


def cmd_watch(args):
    from modules import video
    print(video.analyze(args.source, args.question or "", detail=args.detail,
                        log=not args.no_log))


def cmd_setup(_):
    from modules import setup_wizard
    print(setup_wizard.run())


def cmd_agents(_):
    from modules import subagents
    print(subagents.list_agents())


def cmd_run_agent(args):
    from modules import subagents
    print(subagents.run(args.name, args.task or ""))


def cmd_chat(_):
    import llm
    print("CB Agent strategy chat. Ctrl+C or 'quit' to exit.\n")
    history = []
    while True:
        try:
            q = input("you> ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            break
        if not q or q.lower() in ("quit", "exit"):
            break
        history.append({"role": "user", "content": q})
        text = llm.chat(history, system="You are CB Agent's growth strategist.")
        history.append({"role": "assistant", "content": text})
        print(f"\nagent> {text}\n")


def main():
    p = argparse.ArgumentParser(description="CB Agent — growth automation for clothing brands")
    sub = p.add_subparsers(dest="command")

    sub.add_parser("doctor")
    sub.add_parser("funnel")

    pads = sub.add_parser("ads")
    pads.add_argument("--days", type=int, default=7, choices=[7, 30])
    sub.add_parser("competitors")

    pa = sub.add_parser("advise")
    pa.add_argument("--focus", help="Focus the audit (e.g. 'PDP conversion', 'email flows')")

    pc = sub.add_parser("content")
    pc.add_argument("--stage", default="ALL", choices=["TOF", "MOF", "BOF", "ALL", "tof", "mof", "bof", "all"])
    pc.add_argument("--count", type=int, default=5)
    pc.add_argument("--topic", help="Theme/occasion, e.g. 'July 30 drop week'")

    pr = sub.add_parser("report")
    pr.add_argument("--no-save", action="store_true", help="Print only, don't save to data/reports/")

    pw = sub.add_parser("weekly")
    pw.add_argument("--no-save", action="store_true", help="Print only, don't save to data/weekly/")

    pd = sub.add_parser("debrief")
    pd.add_argument("--date", default="2026-07-30", help="Drop date (YYYY-MM-DD)")
    pd.add_argument("--days", type=int, default=3, help="Window after drop to measure")

    pv = sub.add_parser("videos")
    pv.add_argument("--count", type=int, default=100)

    pi = sub.add_parser("ideas")
    pi.add_argument(
        "--lens",
        default="ALL",
        help="product | content | channels | community | retention | positioning | ops | ALL",
    )
    pi.add_argument("--count", type=int, default=3, help="Ideas per lens (ALL mode)")

    pw = sub.add_parser("watch")
    pw.add_argument("source", help="Video URL or local file path")
    pw.add_argument("question", nargs="?", default="", help="What to analyze")
    pw.add_argument("--detail", choices=["quick", "standard", "deep", "transcript"],
                    default="standard")
    pw.add_argument("--no-log", action="store_true", help="Analyze without logging to competitors.csv")

    sub.add_parser("setup")
    sub.add_parser("agents")

    pra = sub.add_parser("run-agent")
    pra.add_argument("name", help="Subagent name, e.g. content-marketer")
    pra.add_argument("task", nargs="?", default="", help="What you want it to do")

    sub.add_parser("chat")

    pau = sub.add_parser("auth")
    pau.add_argument("action", choices=["status", "meta", "tiktok", "doctor"])

    pg = sub.add_parser("gui")
    pg.add_argument("--port", type=int, default=8377)
    pg.add_argument("--lan", action="store_true",
                    help="Also serve on your local network so your phone can connect")

    args = p.parse_args()
    if not args.command:
        p.print_help()
        sys.exit(0)

    if args.command not in ("doctor", "auth"):
        import tokens
        tokens.ensure_fresh()

    {
        "doctor": cmd_doctor,
        "funnel": cmd_funnel,
        "ads": cmd_ads,
        "competitors": cmd_competitors,
        "advise": cmd_advise,
        "content": cmd_content,
        "report": cmd_report,
        "weekly": cmd_weekly,
        "debrief": cmd_debrief,
        "videos": cmd_videos,
        "ideas": cmd_ideas,
        "watch": cmd_watch,
        "setup": cmd_setup,
        "agents": cmd_agents,
        "run-agent": cmd_run_agent,
        "chat": cmd_chat,
        "auth": cmd_auth,
        "gui": cmd_gui,
    }[args.command](args)


if __name__ == "__main__":
    main()
