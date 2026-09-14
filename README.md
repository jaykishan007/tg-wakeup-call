# Telegram Channel → Phone Call Alert

Rings your phone when a new message is posted in one specific Telegram channel.
See the original build spec for the full rationale; this file is the
step-by-step to get it running.

## Files

- `listener.py` — the always-on process. Watches the channel, calls Twilio.
- `login.py` — one-off interactive script to create `session.session` and
  print channel IDs. Run on your laptop, not the server.
- `.env.example` — copy to `.env` and fill in.
- `telegram-channel-alert.service` — systemd unit for the server.

## Setup

### 1. Telegram API credentials

Get `api_id` / `api_hash` from https://my.telegram.org (API development tools).

### 2. Twilio

1. Sign up at https://www.twilio.com, get **Account SID** and **Auth Token**
   from the console.
2. Buy a **US** phone number with **Voice** capability.
3. If on a trial account, verify your +91 mobile number under
   Phone Numbers → Verified Caller IDs — trial accounts can only call
   verified numbers.

### 3. Local login (on your laptop)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# fill in TG_API_ID and TG_API_HASH in .env

python login.py
```

This prompts for phone number → code → 2FA password, then prints every
dialog you're in with its ID. Find your channel and copy its ID (a negative
number starting `-100`) into `CHANNEL_ID` in `.env`. Fill in the rest of
`.env` (Twilio SID/token, `TWILIO_FROM`, `TWILIO_TO`).

`login.py` writes `session.session` in this directory — that file is your
Telegram account's login credential. Never commit it (already in
`.gitignore`).

### 4. Server

Any small always-on Linux VM works (Oracle Cloud Always Free ARM, Hetzner
CX22, etc). Example with a generic Ubuntu box:

```bash
# on the server
sudo mkdir -p /opt/telegram-channel-alert
sudo chown $USER /opt/telegram-channel-alert

# from your laptop
scp listener.py requirements.txt .env session.session \
    your-user@your-server:/opt/telegram-channel-alert/

# back on the server
cd /opt/telegram-channel-alert
chmod 600 .env session.session
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 5. systemd service

```bash
sudo cp telegram-channel-alert.service /etc/systemd/system/
sudo nano /etc/systemd/system/telegram-channel-alert.service   # fix User= and paths if needed
sudo systemctl daemon-reload
sudo systemctl enable --now telegram-channel-alert
sudo journalctl -u telegram-channel-alert -f
```

## Phone-side setup (required — do this or alerts fail silently)

A US number calling at 3am looks like spam and gets silenced by default.

Save the Twilio number as a contact named `TG ALERT`, then:

- **iPhone**: Contacts → TG ALERT → Edit → Ringtone → **Emergency Bypass** →
  on. Also check Settings → Phone → Silence Unknown Callers is off (or rely
  on the contact's bypass setting).
- **Android**: star the contact, then Settings → Sound → Do Not Disturb →
  Calls → allow **Starred contacts**. Whitelist in Truecaller if installed.

## Test plan

1. **Dry run** — set `DRY_RUN=1` in `.env`, run `python listener.py`, post in
   the channel, confirm it logs what it would dial (no real call placed).
2. **Real call** — set `DRY_RUN=0`, post once, confirm the phone rings,
   respects the ~30s timeout, and comes through with Emergency Bypass.
3. **Cooldown** — post twice in quick succession in a test channel you own,
   confirm the second post is logged as skipped and does not trigger a call.
4. **Resilience** — `sudo reboot` the VM, confirm systemd brings the service
   back on its own (`systemctl status telegram-channel-alert`).

## Notes

- Cooldown state is in-memory only; a restart resets it. Acceptable per spec.
- Unanswered calls aren't billed by Twilio — expect ~$1.15/month (US number
  rental) plus near-zero usage.
- `session.session` and `.env` are full account/credential access. Keep them
  `chmod 600`, never commit them, and keep Telegram 2FA on.
