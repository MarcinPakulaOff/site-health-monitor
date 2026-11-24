# site-health-monitor

A small watchdog for websites: **HTTP status and response time, expected text on the page, SSL certificate expiry and sitemap size**. It alerts on Telegram **when something changes**, not on every run.

## Why "alert on change"

A monitor that pings you every 5 minutes about the same problem gets muted, and then it is useless. Here:

- a check must fail **`fail_after` runs in a row** before it is reported DOWN (one dropped packet is not an alert),
- recovery is reported **once**,
- an unchanged problem is repeated at most every `repeat_hours`.

State is a small JSON file, so a cron or systemd timer can run it every few minutes.

## Usage

```bash
pip install -e .
site-monitor run --config examples/sites.json --state-dir ./state --quiet
site-monitor summary --config examples/sites.json --state-dir ./state   # 7-day uptime summary
```

```json
{
  "fail_after": 2,
  "http": [{"name": "home", "url": "https://example.com/", "contains": "Example", "max_ms": 4000}],
  "ssl": ["example.com"],
  "ssl_warn_days": 14,
  "sitemap": {"url": "https://example.com/sitemap.xml", "min_urls": 10}
}
```

Notifications: set `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`, or `NOTIFY_WEBHOOK_URL` to send through a proxy that keeps the bot token (for example an n8n webhook). Without either, alerts are printed.

It runs in production on my own server, watching my business website.

## Tests

`pytest -q`. The tests start a local HTTP server, so no network is needed. CI: Python 3.10 and 3.12.

## License

MIT
