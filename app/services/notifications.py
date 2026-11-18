import asyncio
import base64
import json
import logging
import smtplib
import ssl
import time
from email.message import EmailMessage
from app.catalog import SERVICE_MAP

log = logging.getLogger('gss.notifications')
DIRECTIONS = {'sto': 'Ремонт на СТО', 'autoelectrician': 'Автоэлектрик', 'help': '🚨 ЗАЯВКА НА ВЫЕЗД', 'corporate': '🏢 КОРПОРАТИВНАЯ ЗАЯВКА'}


def order_text(order):
    p = order['payload_json']
    d, loc, calc = p['data'], p['data']['location'], p['calculator']
    lines = [DIRECTIONS[d['direction']]] if d['direction'] in ('help', 'corporate') else ['🚛 НОВАЯ ЗАЯВКА', DIRECTIONS[d['direction']]]
    lines += ['ID: ' + p['id'], 'Статус: НОВАЯ', 'Создано: ' + p['created_at'],
             'Тип: ' + d['type'], 'Клиент: ' + d['name'], 'Телефон: ' + d['phone'],
             'Email: ' + (d['email'] or 'не указан'),
             'Транспорт: ' + ' '.join([d['vehicle_type'], d['brand'], d['model']]),
             'Услуга: ' + SERVICE_MAP[d['service']]['title'],
             'Проблема / задача: ' + d['description'], 'Комментарий: ' + (d['comments'] or 'нет'),
             'Компания: ' + (d['company'] or '—'), 'ИНН: ' + (d['inn'] or '—'),
             'Автопарк: ' + str(d['fleet_size'] or '—'), 'Адрес: ' + (loc['address'] or 'не указан'),
             'Выезд: ' + ('да' if d['visit'] else 'нет'), 'Срочно: ' + ('да' if d['urgent'] else 'нет')]
    if loc['latitude'] is not None:
        lines += [f"Координаты: {loc['latitude']}, {loc['longitude']}", 'Яндекс Карты: ' + p['map_url']]
    if calc:
        lines += [f"Работа от: {calc['work_from']} ₽; выезд от: {calc['visit_from']} ₽",
                  'Итого: ' + (f"от {calc['total_from']} ₽" if calc['total_from'] is not None else 'индивидуальный расчёт'),
                  f"Расстояние: {calc['distance_km']} км; способ расчёта: {calc['distance_source']}", calc['note']]
    else:
        lines += ['Стоимость: индивидуальное предложение для автопарка']
    lines += [f"Фото: {len(p['photos'])}" if p['photos'] else 'Фото: отсутствуют',
              'Согласие на обработку персональных данных: получено; версия ' + p['consent_version']]
    if d['direction'] == 'help':
        lines += ['Сценарий: клиенту предложено позвонить диспетчеру.']
    return '\n\n'.join(lines)


class Notifications:
    def __init__(self, settings, client, repo, photos):
        self.s, self.client, self.repo, self.photos = settings, client, repo, photos

    async def telegram_api(self, method, **kwargs):
        response = await self.client.post(f'https://api.telegram.org/bot{self.s.telegram_bot_token}/{method}',
                                         timeout=35, **kwargs)
        # Never log HTTP request URLs: the Telegram token is part of the path.
        if not response.is_success:
            raise RuntimeError(f'Telegram HTTP {response.status_code}')
        result = response.json()
        if not result.get('ok'):
            raise RuntimeError('Telegram rejected request')
        return result.get('result')

    async def send_telegram(self, job, order):
        progress = dict(job['progress'])
        ids = list(progress.get('message_ids', []))
        text = order_text(order)
        chunks = [text[i:i + 3800] for i in range(0, len(text), 3800)]
        steps = [('text', chunk) for chunk in chunks]
        loc = order['payload_json']['data']['location']
        if loc['latitude'] is not None:
            steps.append(('location', loc))
        steps += [('photo', item) for item in order['payload_json']['photos']]
        steps.append(('button', None))
        for index, (kind, value) in enumerate(steps):
            if index < progress.get('step', 0):
                continue
            if kind == 'text':
                result = await self.telegram_api('sendMessage', json={'chat_id': self.s.telegram_chat_id, 'text': value})
            elif kind == 'location':
                result = await self.telegram_api('sendLocation', json={'chat_id': self.s.telegram_chat_id,
                    'latitude': value['latitude'], 'longitude': value['longitude']})
            elif kind == 'photo':
                raw = await self.photos.read(value)
                result = await self.telegram_api('sendPhoto', data={'chat_id': self.s.telegram_chat_id,
                    'caption': order['id']}, files={'photo': (value['filename'], raw, 'image/jpeg')})
            else:
                result = await self.telegram_api('sendMessage', json={'chat_id': self.s.telegram_chat_id,
                    'text': 'Обработка заявки ' + order['id'], 'reply_markup': {'inline_keyboard': [[
                        {'text': 'Оформлено', 'callback_data': 'done:' + order['id']}]]}})
            ids.append(result['message_id'])
            progress.update(step=index + 1, message_ids=ids)
            await self.repo.update_job(job['id'], progress=progress, leased_until=time.time() + 300)

    async def send_email(self, job, order):
        text = order_text(order)
        data = order['payload_json']['data']
        subject = f"[ГРУЗСПЕЦСЕРВИС] {DIRECTIONS[data['direction']]} — {order['id']}"
        attachments = [(p['filename'], await self.photos.read(p), 'image/jpeg') for p in order['payload_json']['photos']]
        attachments.append(('order.json', json.dumps(order['payload_json'], ensure_ascii=False, indent=2).encode(), 'application/json'))
        if self.s.mail_transport == 'resend':
            body = {'from': self.s.smtp_from, 'to': [self.s.manager_email], 'subject': subject, 'text': text,
                    'attachments': [{'filename': n, 'content': base64.b64encode(b).decode()} for n, b, _ in attachments]}
            if data['email']:
                body['reply_to'] = data['email']
            result = await self.client.post('https://api.resend.com/emails', json=body,
                headers={'Authorization': 'Bearer ' + self.s.resend_api_key,
                         'Idempotency-Key': 'gss-order-' + order['id']}, timeout=40)
            if not result.is_success:
                raise RuntimeError(f'Email provider HTTP {result.status_code}')
        else:
            message = EmailMessage()
            message['From'], message['To'], message['Subject'] = self.s.smtp_from, self.s.manager_email, subject
            message['Message-ID'] = f"<{order['id']}@gruzspecservice.local>"
            if data['email']:
                message['Reply-To'] = data['email']
            message.set_content(text)
            for filename, raw, content_type in attachments:
                main, sub = content_type.split('/')
                message.add_attachment(raw, maintype=main, subtype=sub, filename=filename)
            await asyncio.to_thread(self.smtp_send, message)

    def smtp_send(self, message):
        connection = smtplib.SMTP_SSL if self.s.smtp_ssl else smtplib.SMTP
        with connection(self.s.smtp_host, self.s.smtp_port, timeout=30) as smtp:
            if not self.s.smtp_ssl:
                smtp.starttls(context=ssl.create_default_context())
            if self.s.smtp_user:
                smtp.login(self.s.smtp_user, self.s.smtp_password)
            smtp.send_message(message)

    async def tick(self):
        for job in await self.repo.claim():
            try:
                order = await self.repo.get(job['order_id'])
                if job['channel'] == 'telegram':
                    if not self.s.telegram_ready:
                        raise RuntimeError('Telegram is not configured')
                    await self.send_telegram(job, order)
                else:
                    if not self.s.email_ready:
                        raise RuntimeError('Email is not configured')
                    await self.send_email(job, order)
                await self.repo.update_job(job['id'], status='sent', leased_until=0, last_error=None)
            except Exception as exc:
                # Persist exception class only; httpx exceptions can contain secret query parameters.
                code = type(exc).__name__
                log.warning('Notification failed order=%s channel=%s error=%s', job['order_id'], job['channel'], code)
                await self.repo.update_job(job['id'], status='failed', leased_until=0,
                    next_at=time.time() + min(3600, 15 * 2**min(job['attempts'], 8)), last_error=code)
        for order in await self.repo.cleanup_candidates():
            jobs = await self.repo.jobs(order['id'])
            if all(j['status'] in ('sent', 'skipped') for j in jobs):
                try:
                    await self.photos.delete(order)
                    await self.repo.update_order(order['id'], photos_cleaned=True)
                except Exception:
                    log.warning('Photo cleanup deferred order=%s', order['id'])

    async def run(self):
        while True:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning('Worker deferred: %s', type(exc).__name__)
            await asyncio.sleep(5)

    async def complete(self, update):
        callback = update.get('callback_query', {})
        message = callback.get('message', {})
        if str(message.get('chat', {}).get('id')) != self.s.telegram_chat_id:
            return
        managers = {i.strip() for i in self.s.telegram_manager_ids.split(',') if i.strip()}
        user_id = str(callback.get('from', {}).get('id', ''))
        if managers and user_id not in managers:
            return
        command = callback.get('data', '')
        if not command.startswith('done:'):
            return
        order_id = command[5:]
        order = await self.repo.get(order_id)
        if not order:
            return
        jobs = await self.repo.jobs(order_id)
        ids = [i for j in jobs if j['channel'] == 'telegram' for i in j['progress'].get('message_ids', [])]
        if message.get('message_id') not in ids:
            return
        await self.repo.update_order(order_id, status='completed', completed_at=time.time(), completed_by=user_id)
        await self.telegram_api('answerCallbackQuery', json={'callback_query_id': callback['id'], 'text': 'Заявка оформлена'})
        try:
            await self.telegram_api('deleteMessages', json={'chat_id': self.s.telegram_chat_id, 'message_ids': ids})
        except Exception:
            # Telegram restricts deletion of older messages. The database completion still stands.
            await self.telegram_api('editMessageText', json={'chat_id': self.s.telegram_chat_id,
                'message_id': message['message_id'], 'text': order_id + ' — оформлено', 'reply_markup': {'inline_keyboard': []}})
