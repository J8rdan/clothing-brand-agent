# CB Agent (Clothing Brand Agent)

> **New here? Read [START-HERE.md](START-HERE.md) instead.**
> It's a complete click-by-click setup guide written for non-technical users.

A local growth agent for clothing/streetwear brands. It reads your Instagram,
ads, store and email list, then tells you what's working and what to post next.
Everything runs on your own machine — nothing is uploaded.

**First run:**
```bash
python agent.py setup     # describe your brand (one time)
python agent.py doctor    # check what's connected
python agent.py gui       # open the Command Center
```


Standalone local agent for scaling a clothing brand: funnel-classifies your content, mines competitor creative patterns, and audits your site/marketing with ranked improvements.

## Setup (5 min)

**New to this?** Open `API-KEYS-GUIDE.html` in the folder — a visual, click-by-click walkthrough of where every API key lives, with diagrams and a progress tracker.


```bash
cd cb-agent
pip install -r requirements.txt
cp .env.example .env
# open .env and paste your ANTHROPIC_API_KEY (console.anthropic.com)
python agent.py doctor
```

Only the Anthropic key is required. Instagram/Meta/Shopify tokens are optional — everything degrades gracefully to manual data.

## Commands

| Command | What it does |
|---|---|
| `python agent.py doctor` | Shows which connectors are live |
| `python agent.py funnel` | Tags every recent post TOF/MOF/BOF, shows your mix vs. engagement per stage, then gives a strategic read + post ideas for under-served stages |
| `python agent.py competitors` | Analyzes winning patterns from competitor posts you've logged and generates 10 ranked on-brand adaptations |
| `python agent.py advise` | Full site + marketing audit, top 5 improvements ranked by impact × ease, quick wins, one thing to stop |
| `python agent.py advise --focus "PDP conversion"` | Focused audit |
| `python agent.py content --stage BOF --count 5 --topic "drop week"` | Generate funnel-targeted post concepts with hooks, shot lists, and captions |
| `python agent.py report` | Daily 2-minute brief: headline, day-over-day changes, content/funnel status, ads, competitor patterns, top 3 actions, one metric to watch. Saves to `data/reports/` so it tracks history |
| `python agent.py weekly` | Weekly review led by Klaviyo list growth: subscribers joined this week (email vs SMS split), total size, pace vs last week, plus content recap and next week's plan. Saves to `data/weekly/` |
| `python agent.py debrief --date 2026-07-30` | Post-drop debrief: exact sales numbers reconciled against list size, ad spend, and content (waitlist conversion %, revenue per subscriber, revenue per ad dollar), then an honest verdict, leak analysis, and a 5-point playbook for the next drop. Works without Shopify — it'll ask you to type the topline numbers. Saves to `data/debriefs/` |
| `python agent.py videos` | 100 fresh video ideas per run, grouped TOF/MOF/BOF with hooks, formats, and effort ratings — plus a TOP 10 shortlist of what to shoot today. Logs every idea ever generated so it never repeats across days. Saves to `data/video_ideas/`. For a daily 100, add a Task Scheduler job with arguments `agent.py videos` |
| `python agent.py ideas` | Scans 7 lenses (product, content, channels, community, retention, positioning, ops) for opportunities you might be missing, ranked by fit x payoff / effort |
| `python agent.py ideas --lens retention --count 5` | Deep-dive one lens |
| `python agent.py chat` | Free-form strategy chat with full brand context loaded |
| `python agent.py gui` | **Command Center** — opens a dark themed dashboard in your browser: every command as a button, chat bar, connector status, and your report history. On Windows just double-click `2 - START AGENT.bat` |


The agent can edit your Shopify theme in plain English and show you a preview before anything goes live:

```bash
python agent.py site status                      # themes + preview link
python agent.py site ideas                       # improvements grounded in your actual theme code
python agent.py site publish --yes               # draft -> live (explicit step)
python agent.py site rollback --file sections/drop-hero.liquid
```

Or use the **Website** section in the Command Center — describe the change, it applies to the draft, and a live preview embeds right in the dashboard with an open-in-new-tab link.

Safety model: **one-time setup** — in Shopify admin, duplicate your live theme and rename it to include "draft" or "agent". All edits go to that draft; your live site never changes until you publish. Every edited file is backed up locally first, so `rollback` can always undo. The custom app token needs `read_themes` + `write_themes` scopes added.

## Feeding it data (manual mode)

**Your IG posts** → `data/my_posts.csv` | **Your TikToks** → `data/my_tiktoks.csv` (columns: `caption,views,likes,comments,shares,saves,posted_at,url`)

IG columns:
Columns: `caption,media_type,likes,comments,saves,shares,reach,views,posted_at,url`
Pull these numbers from IG Insights on your phone — 10–20 recent posts is plenty. A sample file with two rows is included; replace it with your real data.

**Competitor creatives** → `data/competitors.csv`
Columns: `brand,post_description,format,hook,views_or_likes,why_it_worked,url`
Workflow: 15 min in your Explore feed, log ~10 posts from dark/minimal streetwear or jewelry brands that clearly popped. The agent extracts the *mechanisms* and rebuilds them in your brand's voice — it never copies creative.

**Or just brand names** → `data/competitor_brands.txt` (one per line) if you haven't logged posts yet.

## Connecting APIs (optional, later)

- **TikTok Display API**: create an app at developers.tiktok.com, get a user token with `video.list` scope, set `TIKTOK_ACCESS_TOKEN`. Auto-pulls your videos with views/likes/comments/shares into `funnel` and `report`.
- **Instagram Graph API**: needs a Meta app, your IG business account ID, and a long-lived token with `instagram_basic` + `instagram_manage_insights`. Fills `funnel` automatically.
- **Meta Marketing API**: token with `ads_read` + your `act_XXXXXXXX` account ID. Grounds `advise` in real ad performance.
- **Klaviyo**: Settings -> API keys -> create a **private** key (read-only scope for Lists + Profiles is enough), set `KLAVIYO_PRIVATE_KEY` in .env. `KLAVIYO_LIST_ID` defaults to your waitlist. Note: the public site key from your signup forms cannot read data — it must be a private key.
- **Shopify Admin API**: create a custom app in Shopify admin → API credentials → Admin API token with `read_products`, `read_orders`. Grounds `advise` in real store data.

## How the funnel classification works

- **TOF** — discovery: philosophy, motion, trend adaptation, no selling
- **MOF** — consideration: craft, BTS, styling, product education
- **BOF** — conversion: drop urgency, offers, social proof, direct CTA

The classifier also tags each post's hook type and CTA strength, so the strategic read can tell you not just *what stage* you're over/under-serving but *why* specific posts under-performed.

## Costs

Each command makes 1–2 Claude API calls (~$0.01–0.05 per run at typical sizes). The `funnel` command on 30 posts is the heaviest.

## Token setup & auto-refresh

Once your developer apps are approved:

```bash
python agent.py auth meta      # paste your long-lived token once; verified & stored
python agent.py auth tiktok    # guided OAuth login in your browser
python agent.py auth status    # check token ages anytime
```

Add the refresh credentials to `.env` (from each app's dashboard): `META_APP_ID`, `META_APP_SECRET`, `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`, `TIKTOK_REDIRECT_URI`.

After that, every command auto-refreshes tokens before running — Meta's 60-day token renews at 40 days, TikTok's 24-hour token renews at 20 hours. As long as the daily report runs, nothing ever expires. Tokens are stored in `data/tokens.json` (never commit or share this file — treat it like a password).

## Watching / analyzing videos

```bash
python agent.py watch <url-or-path> "what should I analyze?"
python agent.py watch https://youtube.com/... "break down the hook" --detail deep
```

Or use **WCH (Watch video)** in the Command Center: paste a link, add a question, pick a detail level, hit Analyze.

It downloads the video (yt-dlp), extracts frames (ffmpeg), pulls a transcript from captions, then Claude analyzes the actual frames and audio against your brand's content strategy — hook, pacing, and adaptable takeaways.

**One-time setup** — two binaries the agent shells out to:
- `yt-dlp`: `pip install yt-dlp` (or it is in requirements.txt)
- `ffmpeg`: download the "release full" build from gyan.dev/ffmpeg/builds, unzip, add the \bin folder to PATH, restart your terminal

Optional: a Whisper API key (Groq or OpenAI) transcribes videos that have no captions. Without it, captioned videos still work and others fall back to frames-only. The `watch` command prints exact setup steps if a binary is missing.

When you analyze a video by URL, the agent also extracts the brand, hook, and why-it-worked and appends a row to `data/competitors.csv` automatically — so your competitor dataset builds itself and the `competitors` command and content subagents get smarter over time. Untick "log to competitors" (or pass `--no-log`) to skip. Re-analyzing the same URL won'''t double-log.

A note on scope: analyzing others''' videos is for private study. Downloaded files are deleted right after analysis.

## Themes

Six colorways, switchable from the THEME button or Ctrl+K → "theme". Your choice is remembered.

| Theme | Look |
|---|---|
| Jarvis HUD | cyan holographic (default) |
| Arc Reactor | deep teal, reactor glow |
| Mono | black and white |
| Steel | dark steel palette |
| Voxel | blocky pixel world |
| Dojo | sumi ink, red seal |

Every theme re-skins the whole interface — boot sequence, orbital core, panels, meters and report typography.

## Subagents (specialist personas)

Drop Claude Code style `.md` agent files into the `agents/` folder and the agent loads them automatically.

```bash
python agent.py agents                                    # list installed
python agent.py run-agent content-marketer "plan drop week content"
python agent.py run-agent multi-agent-coordinator "sequence the work for drop week"
```

Or use the **Specialists** section in the Command Center — pick an agent from the dropdown, type the task, hit Run.

Each file's frontmatter is respected: the `model:` line routes to the right Claude model (`haiku` -> claude-haiku-4-5, `sonnet` -> claude-sonnet-5, `opus` -> claude-opus-5), and the body becomes the system prompt. Your brand context and live data (post counts, Klaviyo list size, logged competitors) are injected automatically, along with a roster of the other installed subagents — so coordinator-style agents plan with agents that actually exist rather than inventing teammates.

One honest limitation: these files were written for Claude Code, where the agent can call tools like Read/Write/WebSearch. Here it runs as a persona without tool access, so it's told plainly it can't browse or read files and should say what data it needs rather than invent numbers. The same file also sits in `.claude/agents/` — when you use Claude Code on this folder, it works there *with* full tool access.

## Using it on your phone

Three options, easiest first:

1. **Read reports** — keep the folder in OneDrive/Google Drive and open `data/reports/YYYY-MM-DD.md` in the drive app. Zero setup, works anywhere.
2. **Full Command Center on home Wi-Fi** — double-click `4 - START (phone access).bat` on your PC, then open the `http://192.168.x.x:8377` address it prints on your phone. Both devices must be on the same Wi-Fi, and the PC must stay on. Note: anyone on that Wi-Fi can reach it, and there is no password — home network only.
3. **From anywhere** — install Tailscale (free) on both PC and phone, then use the LAN mode above with your PC's Tailscale address. Encrypted, private to your devices.

## Automating the daily report (Windows 11)

Task Scheduler -> Create Basic Task -> Daily at your morning time -> Start a Program:
- Program: `python`
- Arguments: `agent.py report`
- Start in: full path to the `cb-agent` folder

For the weekly review, add a second Task Scheduler job: weekly on Sunday, arguments `agent.py weekly`.

Reports accumulate in `data/reports/YYYY-MM-DD.md`, and each new report reads the previous one so it reports day-over-day change instead of repeating itself.
