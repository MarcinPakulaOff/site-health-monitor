"""Send a message to Telegram — directly with a bot token, or through a webhook proxy.

TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID  -> api.telegram.org sendMessage
NOTIFY_WEBHOOK_URL                     -> POST {"method": "sendMessage", "payload": {...}}
                                          (a proxy that holds the token, e.g. an n8n webhook)
neither                                -> print to stdout
"""

from __future__ import annotations

import json
import os
import urllib.request


def _post(url: str, body: dict) -> None:
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        resp.read()


def send(text: str) -> str:
    """Deliver `text` (Telegram HTML). Returns the channel used."""
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    payload = {"text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if token and chat:
        _post(f"https://api.telegram.org/bot{token}/sendMessage", {"chat_id": chat, **payload})
        return "telegram"
    hook = os.environ.get("NOTIFY_WEBHOOK_URL")
    if hook:
        _post(hook, {"method": "sendMessage", "payload": payload})
        return "webhook"
    print(text)
    return "stdout"
