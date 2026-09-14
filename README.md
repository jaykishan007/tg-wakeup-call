# Telegram Channel → Phone Call Alert

Rings your phone via Twilio whenever a new post appears in one Telegram
channel. See `listener.py` for how it works.

## Local run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# fill in .env: Telegram api_id/api_hash, Twilio SID/token/numbers

python login.py       # interactive: phone -> code -> 2FA
                       # creates session.session, prints every dialog + its ID

DRY_RUN=1 python listener.py   # confirm it detects posts without calling
python listener.py             # real run
```

`session.session` is full access to your Telegram account — never commit it
(already in `.gitignore`), keep it `chmod 600`.

### Finding CHANNEL_ID

`login.py`'s dialog list prints an ID and a `kind` (channel/group/user) next to
each chat's title. Two things to watch for:

- **Broadcast channels and their linked comments group can look identical** —
  Telegram's discussion group behind a channel is technically also a
  "channel" (a supergroup), so `login.py` may label both `channel`. Picking
  the discussion group by mistake means you'd get called for every comment,
  not just new posts. If unsure which is which, ask, or check in the Telegram
  app: the discussion group is the one with a chat-bubble icon and normal
  member list; the broadcast channel is the one you can't reply in directly.
- **The ID needs a `-100` prefix.** Telegram's raw channel ID is a plain
  positive number; Telethon (and the ID you paste into `CHANNEL_ID`) needs it
  as a negative number prefixed with `100`, e.g. raw `3940583658` becomes
  `-1003940583658`. `login.py` already prints it in this ready-to-use form.

## Deploy (Fly.io)

```bash
fly auth login
fly apps create <app-name>              # edit `app =` in fly.toml to match
fly secrets import < .env               # pushes .env as encrypted secrets
fly deploy
fly logs                                # confirm it connects and listens
```

`session.session` is baked into the Docker image at build time (`Dockerfile`),
so it must exist locally before deploying. `fly.toml` deliberately has no
`http_service`/`services` block — this app makes outbound connections only
(Telegram, Twilio), so there's no inbound traffic for Fly's proxy to base an
autostop-on-idle decision on; the machine just runs continuously.

A `telegram-channel-alert.service` systemd unit is also included as an
alternative if you'd rather run this on a plain VM instead of Fly.
