# CB Agent — Start Here

This guide assumes you have never done anything like this before.
Every step tells you exactly what to click and what you should see.

**Total time:** about 30 minutes. You only do this once.

If a step doesn't look like what's described, stop and ask — don't guess.

---

## What this thing is

CB Agent is a program that runs **on your own computer**. It looks at your
brand's Instagram, ads, store and email list, and tells you what's working,
what isn't, and what to post next.

Nothing is uploaded anywhere. Your keys and data stay on your machine.

---

## Before you start, you need

1. **A Windows PC** (this guide is for Windows)
2. **About 30 minutes**
3. **A credit card** — for one service (Anthropic). Expect roughly **$5–15/month**
   for normal use. Everything else is free.

---

# PART 1 — Put the folder somewhere permanent

**This matters more than it sounds.** If you leave this in Downloads, you will
lose your settings later. Do this properly now and you never think about it again.

### Step 1.1 — Make your folder

1. Press the **Windows key** on your keyboard
2. Type `File Explorer` and press **Enter**
3. In the bar at the top, type this and press **Enter**:
   ```
   C:\Users\%USERNAME%
   ```
   This opens your personal folder. You have full permission here.
4. Right-click on any empty white space
5. Choose **New** → **Folder**
6. Name it exactly: `cb-agent`
7. Press **Enter**

You now have a folder at `C:\Users\<your name>\cb-agent`.

### Step 1.2 — Put the program inside it

1. Find the `cb-agent.zip` file you downloaded
2. Right-click it → **Extract All…** → **Extract**
3. Open the extracted folder. You should see files like `agent.py`,
   `2 - START AGENT.bat`, and folders called `modules` and `data`
4. Select **everything** (click one file, then press **Ctrl + A**)
5. **Ctrl + C** to copy
6. Go back to your `cb-agent` folder from Step 1.1
7. **Ctrl + V** to paste

> ✅ **Check:** open `C:\Users\<your name>\cb-agent` — you should see `agent.py`
> sitting right there, not inside another folder.

**From now on, this folder is the only one you use.** Ignore anything left in Downloads.

---

# PART 2 — Install Python

Python is the engine the agent runs on. It's free.

### Step 2.1 — Download it

1. Go to **https://www.python.org/downloads/**
2. Click the big yellow **Download Python** button
3. When it finishes, click the downloaded file to run it

### Step 2.2 — The one checkbox that matters

On the first installer screen, at the **bottom**, there is a checkbox:

> ☑ **Add python.exe to PATH**

**Tick it.** If you miss this, nothing else in this guide will work.

Then click **Install Now** and wait. When it says "Setup was successful", click **Close**.

### Step 2.3 — Check it worked

1. Press the **Windows key**, type `cmd`, press **Enter** — a black window opens
2. Type this and press Enter:
   ```
   python --version
   ```

**What you should see:** something like `Python 3.13.1`

**If instead you see** "Python was not found" or a Microsoft Store window opens:
- Try `py --version` instead. If *that* works, use `py` everywhere in this guide
  wherever it says `python`.
- If neither works, re-run the Python installer, choose **Modify**, and make sure
  **Add python.exe to PATH** is ticked. Then restart your PC.

---

# PART 3 — Install the agent

1. Open your `cb-agent` folder in File Explorer
2. Find the file called **`1 - SETUP (run once).bat`**
3. **Double-click it**

A black window opens and text scrolls past. This is installing what the agent needs.

**Wait for it to finish** — it will say something like "Setup complete" and ask you
to press a key.

> ⚠️ If Windows shows a blue "Windows protected your PC" box:
> click **More info** → **Run anyway**. This happens because the file isn't
> signed by a big company; it's safe.

---

# PART 4 — Tell the agent about your brand

This is what makes the advice actually about *your* brand.

1. Open a black command window **in your cb-agent folder**:
   - Open the `cb-agent` folder in File Explorer
   - Click once on the **address bar** at the top (the strip showing the folder path)
   - Type `cmd` over it and press **Enter**
   - A black window opens, already in the right place

2. Type this and press Enter:
   ```
   python agent.py setup
   ```

3. It asks you 9 questions about your brand — name, what you sell, what you stand
   for, your look, your main product, who buys from you, your channels.

   **Answer in plain English.** Press Enter to skip anything you're unsure about.
   You can change all of it later.

> ✅ **Check:** it finishes by saying "SAVED" and shows you where your profile lives.

You can edit that file any time: it's `data\brand.txt` in your folder — open it
with Notepad.

---

# PART 5 — Get your API key (the important one)

An "API key" is a password that lets the agent use Claude's brain. Without it,
nothing works.

### Step 5.1 — Make an account

1. Go to **https://console.anthropic.com**
2. Sign up (or log in)
3. This is a **separate account and separate bill** from a Claude.ai subscription.
   Having Claude Pro does not cover this.

### Step 5.2 — Add money

1. Find **Billing** in the left menu (or under Settings)
2. Add a payment method and put **$5–10** on it to start
3. Typical use is a few dollars a month. You are only charged for what you use.

### Step 5.3 — Create the key

1. Click **API keys** in the left menu
2. Click **Create Key**
3. Give it a name like `cb-agent`
4. **Copy the key immediately** — it starts with `sk-ant-` and you can only see it once
5. Paste it somewhere temporarily (a Notepad window) so you don't lose it

### Step 5.4 — Put the key in the agent

The file you need is **already in your folder**. You just fill it in.

1. In your `cb-agent` folder, find the file called **`.env`**
   (it has no icon and no file extension — that's normal)
2. Right-click it → **Open with** → **Notepad**
   - If Windows asks "How do you want to open this file?", scroll down and
     pick **Notepad**, then click OK
3. Scroll to the line that says:
   ```
   ANTHROPIC_API_KEY=
   ```
4. Paste your key **immediately after the `=`**, with **no space**:
   ```
   ANTHROPIC_API_KEY=sk-ant-your-key-here
   ```
5. **Save** with Ctrl + S, then close Notepad

That's the only key you need to start. The rest of the file is optional
connectors you can fill in later — it's all explained inside the file.

> ⚠️ **Do not rename this file or save it as something else.** If Notepad
> tries to save it as `.env.txt`, choose **Save as** → set "Save as type" to
> **All Files** → name it exactly `.env`.
>
> To see real file names, click **View** at the top of File Explorer and tick
> **File name extensions**.

### Step 5.5 — Check it worked

In your black command window:
```
python agent.py doctor
```

**What you should see:**
```
OK Anthropic API  (required)
```

If it says `--` instead of `OK`, your key isn't being read. Check:
- Is the file named exactly `.env` (not `.env.txt`)?
- Is it in the same folder as `agent.py`?
- Is there a space after the `=`? There shouldn't be.

---

# PART 6 — Start using it

You're done with the required setup. To open the agent:

**Double-click `2 - START AGENT.bat`**

Your web browser opens with the Command Center. Leave the black window open in
the background — closing it turns the agent off.

### Try these first

- Click **RPT (Daily report)** — your first brief
- Click **CNT (Content)** — post ideas for your brand
- Click **WCH (Watch video)** — paste any video link and it breaks down why it worked
- Type a question in the bar at the bottom and hit Send

---

# PART 7 — Optional: connect your accounts

Everything above works without these. Connect them when you want real numbers
instead of general advice.

Double-click **`3 - API KEY GUIDE.bat`** for a visual walkthrough of each one.

| What | Gives you | Difficulty |
|---|---|---|
| **Klaviyo** | Email/SMS list growth tracking | Easy — 5 min |
| **Shopify** | Real orders and revenue in your reports | Medium — 10 min |
| **Instagram** | Your real post performance and funnel analysis | Hard — 20 min |
| **Meta Ads** | Ad performance, scale/kill calls | Comes with Instagram |
| **TikTok** | TikTok analytics | Needs TikTok's approval — days |

**Suggested order:** Klaviyo → Shopify → Instagram. Do them one at a time,
and run `python agent.py doctor` after each to confirm it worked.

---

# Everyday use

| I want to… | Do this |
|---|---|
| Open the agent | Double-click `2 - START AGENT.bat` |
| Check what's connected | `python agent.py doctor` |
| Change my brand info | `python agent.py setup`, or edit `data\brand.txt` |
| Get today's brief | Click **RPT** in the app |
| Analyze a video | Click **WCH**, paste the link |
| Close it | Close the black window |

---

# When something breaks

### "python is not recognized"
Use `py` instead of `python`. If that fails, reinstall Python with
**Add python.exe to PATH** ticked, then restart your PC.

### Everything says "standby" in doctor
Your `.env` file isn't being read. Nine times out of ten it's named `.env.txt`.
Turn on **File name extensions** in File Explorer's View menu and check.

### The browser page says "Failed to fetch"
The agent stopped running. Check the black window is still open — if you closed
it, double-click `2 - START AGENT.bat` again and refresh the page.

### Instagram stops working after a while
Meta logins expire. Run:
```
python agent.py auth meta
```
and paste a fresh token. Run `python agent.py auth doctor` to see what's wrong.

### It worked before and now nothing is connected
You're probably running from a different copy of the folder. Your settings live
in `.env` and the `data` folder — they don't travel with a fresh download.
**Always run from `C:\Users\<your name>\cb-agent`.**

---

# Updating later

When you get a new version, **do not** just unzip it and run it — you'll lose
your settings.

Instead:
1. Unzip the new version somewhere temporary
2. Copy the new files into your `cb-agent` folder, overwriting when asked
3. **Do not copy over** your `.env` file or your `data` folder — those are yours

Your brand profile, keys, logins, and report history all live in `.env` and
`data\`. Keep those and everything else can be replaced freely.

---

# Your files, explained

| File / folder | What it is |
|---|---|
| `.env` | **Your API keys.** Already in the folder — just fill it in. Private, never share it. |
| `data\brand.txt` | **Your brand profile.** Edit any time. |
| `data\` | Your reports, logins, and history. Back this up. |
| `2 - START AGENT.bat` | Opens the app |
| `agent.py` | The program itself — don't edit |

---

**Rule of thumb:** if you're ever unsure whether something is safe to delete,
it isn't. Keep `.env` and `data\`, and you can always recover everything else.
