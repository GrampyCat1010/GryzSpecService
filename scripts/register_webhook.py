"""Register the Telegram callback URL from .env; prints no bot token."""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from app.config import Settings


async def main():
    s = Settings()
    if not s.telegram_bot_token or not s.telegram_webhook_secret or not s.public_url.startswith('https://'):
        raise SystemExit('Set TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET and HTTPS PUBLIC_URL first.')
    async with httpx.AsyncClient() as client:
        response = await client.post(f'https://api.telegram.org/bot{s.telegram_bot_token}/setWebhook', json={
            'url': s.public_url.rstrip('/') + '/api/telegram/webhook',
            'secret_token': s.telegram_webhook_secret, 'allowed_updates': ['callback_query']}, timeout=20)
        if response.status_code != 200 or not response.json().get('ok'):
            raise SystemExit('Telegram rejected webhook registration. Check token, URL and TLS.')
    print('Webhook registered.')

if __name__ == '__main__':
    asyncio.run(main())
