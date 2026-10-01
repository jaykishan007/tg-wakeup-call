# Telegram Channel → Phone Call Alert

Get a **real phone call** when a Telegram channel posts a trade signal, so you
don't miss it when your phone is on silent or you're asleep.

It watches one Telegram channel. When a new post looks like a trade
instruction ("Open long #BTC", "Close", "Stoploss at 2$", "Add 10k",
"Round 2", ...), it calls your phone through Twilio and reads the message
out loud. Chatter like "+30%" or "Crazy." is ignored.

```
Telegram channel ──new post──▶ listener.py ──is it a trade signal?──▶ Twilio ──▶ your phone rings
```

> **Using Claude (or another AI assistant) to set this up?** Jump to
> [Setting it up with Claude](#setting-it-up-with-claude).

---

## What you need

| Thing | Why | Cost |
|---|---|---|
| A Telegram account that has joined the channel | The script reads the channel *as you* | Free |
| Telegram API ID + hash | Lets the script log in to your account | Free |
| A Twilio account + Twilio phone number | Places the phone call | Paid per call (trial credit to start) |
| Python 3.10 or newer | Runs the script | Free |
| *(Optional)* A Fly.io account | Keeps it running 24/7 in the cloud | Small monthly cost, card required |

You can run it on your own computer first. It only works while that computer
is on and awake, so move it to Fly.io (Step 6) once it works.

---

## Step 1: Get your Telegram API ID and hash

1. Go to <https://my.telegram.org> and log in with your phone number.
2. Click **API development tools**.
3. Fill in the form (any app name and short name, e.g. `channel-alert`;
   platform can be "Other").
4. Copy the **App api_id** (a number) and **App api_hash** (a long string).

Keep the hash private. It's half of what's needed to log in as you.

## Step 2: Set up Twilio

1. Sign up at <https://www.twilio.com/try-twilio>.
2. From the **Console** home page, copy your **Account SID** and **Auth Token**.
3. Get a phone number: **Phone Numbers → Manage → Buy a number**, and pick
   one with **Voice** capability. This is the number that will call you.
4. **Allow calls to your country**: go to **Voice → Settings → Geo
   permissions** and tick the country of *your* mobile number (e.g. India).
   Without this, calls fail silently.
5. **Trial accounts only:** Twilio can only call numbers you've verified.
   Go to **Phone Numbers → Manage → Verified Caller IDs** and add your
   mobile. Trial calls also play a short Twilio message first and ask you to
   press a key before reading the alert. Upgrading the account removes this.

## Step 3: Download the code and install it

You need [Python 3.10+](https://www.python.org/downloads/) and
[git](https://git-scm.com/downloads). Then, in a terminal:

```bash
git clone https://github.com/jaykishan007/tg-wakeup-call.git
cd tg-wakeup-call

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Step 4: Fill in your settings

```bash
cp .env.example .env
```

Open `.env` in a text editor and fill it in. Leave `CHANNEL_ID` empty for
now; Step 5 finds it.

| Setting | What to put | Example |
|---|---|---|
| `TG_API_ID` | api_id from Step 1 | `12345678` |
| `TG_API_HASH` | api_hash from Step 1 | `0123abcd...` |
| `CHANNEL_ID` | Filled in during Step 5 | `-1001234567890` |
| `TWILIO_ACCOUNT_SID` | From Twilio console | `AC...` |
| `TWILIO_AUTH_TOKEN` | From Twilio console | |
| `TWILIO_FROM` | Your Twilio number, with `+` and country code | `+15551234567` |
| `TWILIO_TO` | Your mobile, with `+` and country code | `+919876543210` |
| `COOLDOWN_MINUTES` | After a call, ignore new signals for this long so a burst of posts doesn't ring you 5 times | `3` |
| `DRY_RUN` | `1` = only log what it *would* do, `0` = really call | `1` while testing |

No spaces around `=`, and no quotes.

## Step 5: Log in to Telegram and find the channel ID

```bash
python login.py
```

It asks for your phone number, then the login code Telegram sends you (in
the Telegram app), then your 2-step verification password if you have one.

When it's done, it:

- creates a file called **`session.session`**, which is your logged-in
  Telegram session, and
- prints every chat you're in, with its ID.

Find your channel in that list and copy its ID (it starts with `-100`) into
`CHANNEL_ID` in `.env`.

> **Watch out:** many channels have a linked **discussion/comments group**
> with almost the same name, and both show up as `channel`. Pick the one
> where only the admin posts. If you pick the comments group, you'll be
> called for every comment.

> **Keep `session.session` secret.** Anyone with this file can use your
> Telegram account. Never commit it, upload it, or send it to anyone.
> (`.gitignore` already keeps it out of git.)

### Test it

```bash
DRY_RUN=1 python listener.py
```

You should see `Connected. Listening for new messages in channel ...`. When
the channel posts, the log will show either `skipping (not an actionable
trade signal)` or `DRY_RUN: would call ...`.

When that looks right, set `DRY_RUN=0` in `.env` and run it for real:

```bash
python listener.py
```

Press `Ctrl+C` to stop.

## Step 6: Run it 24/7 on Fly.io (optional)

1. Install the Fly CLI: <https://fly.io/docs/flyctl/install/>
2. Log in and create an app. The name must be unique across all of Fly, so
   pick your own:

   ```bash
   fly auth login
   fly apps create my-channel-alert
   ```

3. Open `fly.toml` and change the `app = "..."` line to the name you picked.
4. Upload your settings as encrypted secrets, then deploy:

   ```bash
   fly secrets import < .env
   fly deploy
   fly logs        # should show "Connected. Listening for new messages..."
   ```

`session.session` is copied into the app when you run `fly deploy`, so it
must exist (Step 5) before you deploy.

> **Stop the local copy once it's on Fly.** Running the same
> `session.session` in two places at once can make Telegram cancel the
> session, and then you'd have to log in again (Step 5) and redeploy.

### Changing things later

| To... | Run |
|---|---|
| Change a setting (e.g. cooldown) | `fly secrets set COOLDOWN_MINUTES=5` (restarts automatically) |
| Deploy code changes | `fly deploy` |
| See what it's doing | `fly logs` |
| Stop it | `fly scale count 0` (start again with `fly scale count 1`) |

A `telegram-channel-alert.service` file is also included if you'd rather
run it on your own Linux server with systemd instead of Fly.

---

## Which posts trigger a call?

The rules live in `is_actionable()` in `listener.py`. They were tuned for
**one specific channel's** writing style. A post triggers a call if it
contains any of:

- `open long`, `open short`, `order limit`, `close`, `cancel`, `stoploss` /
  `stop-loss`, `entry`, `buy`, `add`
- `short` or `long` right before a ticker, like `Short #BTC` or `long $ZEC`
- `short` or `long` together with `vol` or `capital`
- `round 2`, `round3`, ... in a short post (10 words or fewer) that isn't a
  profit update like `Round 2 +25%`

**If you follow a different channel, you'll probably need to change these
rules** to match how that channel writes. The easiest way is to give an AI
assistant a few weeks of the channel's posts and ask it to adjust
`is_actionable()` (see below). To get a call for *every* post instead, make
`is_actionable()` return `True` for any non-empty text.

---

## Troubleshooting

| Problem | Likely cause |
|---|---|
| `KeyError: 'TG_API_ID'` (or another name) | That line is missing or empty in `.env` (or in Fly secrets) |
| Runs, but never logs anything when the channel posts | Wrong `CHANNEL_ID`, often the comments group instead of the channel |
| Logs "skipping (not an actionable trade signal)" for a post you wanted | The filter rules don't match that wording; see the section above |
| Logs "cooldown active" | A call was placed less than `COOLDOWN_MINUTES` ago |
| Logs "Call placed" but your phone doesn't ring | Twilio Geo permissions (Step 2.4), unverified number on a trial account (Step 2.5), or your carrier blocking it. Check **Monitor → Logs → Calls** in Twilio |
| Asks for a phone number / login when running on Fly | `session.session` is missing or was cancelled. Run `login.py` again locally, then `fly deploy` |

---

## Setting it up with Claude

You can hand this repo to [Claude Code](https://claude.com/claude-code) (or a
similar AI coding assistant) and have it walk you through everything. For
example:

> Clone `https://github.com/jaykishan007/tg-wakeup-call` and help me set it up. I want a phone call when
> the Telegram channel "<channel name>" posts a trade signal. My mobile is in
> <country>. Walk me through it step by step and run what you can for me.

Some steps **must be done by you**. An assistant can't do these for you:

- creating the Telegram API app at my.telegram.org (Step 1),
- signing up for Twilio, buying a number, and changing Geo permissions (Step 2),
- typing the Telegram login code and 2FA password when `login.py` asks (Step 5),
- `fly auth login` and adding a payment card to Fly (Step 6).

**Notes for the AI assistant:**

- `login.py` is interactive (phone → code → 2FA). Have the user run it in
  their own terminal; don't try to answer its prompts yourself.
- Never print, commit, or upload `.env` or `session.session`. Both are
  credentials. Read `.env` values only to check whether they're filled in.
- Test with `DRY_RUN=1` before the first real call.
- The filter in `is_actionable()` is tuned for one channel. If the user
  follows a different one, offer to pull recent posts with Telethon (reusing
  `session.session`) and tune the rules against them. Show which posts
  would and wouldn't call before changing anything.
- Don't run the listener locally while it's also deployed. Two clients on
  one session can get it cancelled by Telegram.
