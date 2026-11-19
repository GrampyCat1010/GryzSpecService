import asyncio
import io
import json
import uuid
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import Settings
from app.main import create_app


@pytest.fixture
def client(tmp_path):
    settings = Settings(_env_file=None, database_path=str(tmp_path / 'test.db'), worker_enabled=False)
    app = create_app(settings)
    with TestClient(app, raise_server_exceptions=False) as browser:
        app.state.photos.root = tmp_path / 'photo'
        yield browser


def payload(**overrides):
    data = dict(name='Иван', phone='+7 (999) 123-45-67', brand='КАМАЗ', model='5490',
                description='Не запускается двигатель', consent=True)
    data.update(overrides)
    return data


def send(client, data=None, key=None, photos=None, endpoint='/api/orders'):
    return client.post(endpoint, data={'payload': json.dumps(data or payload())},
                       files=photos, headers={'Idempotency-Key': key or str(uuid.uuid4())})


def photo():
    stream = io.BytesIO()
    Image.new('RGB', (80, 50), '#ed2020').save(stream, format='PNG')
    return stream.getvalue()


def run(client, awaitable):
    return client.portal.call(lambda: awaitable)


def test_canonical_record_idempotency_and_conflict(client):
    key = str(uuid.uuid4())
    response = send(client, key=key)
    assert response.status_code == 201
    order_id = response.json()['data']['order_id']
    again = send(client, key=key)
    assert again.status_code == 200
    assert again.json()['data']['order_id'] == order_id
    conflict = send(client, payload(description='Теперь другая неисправность'), key=key)
    assert conflict.status_code == 409
    order = run(client, client.app.state.repo.get(order_id))
    assert order['payload_json']['data']['phone'] == '+79991234567'
    assert order['payload_json']['calculator']['total_from'] == 10000
    assert order['payload_json']['id'] == order_id
    assert order['status'] == 'new'


@pytest.mark.parametrize('changes', [dict(phone='123'), dict(consent=False), dict(brand=''),
    dict(service='unknown'), dict(service='help'), dict(location={'latitude': 50}),
    dict(website='spam.example'), dict(type='corporate', company='ООО Тест')])
def test_invalid_orders_are_never_saved(client, changes):
    assert send(client, payload(**changes)).status_code == 422
    assert client.app.state.repo.db.execute('select count(*) from orders').fetchone()[0] == 0


def test_help_direction_is_derived_on_server_and_address_is_enough(client):
    response = send(client, payload(service='towing', direction='sto', visit=False,
                                   location={'address': 'Трасса М5, 320 км'}))
    assert response.status_code == 201
    row = run(client, client.app.state.repo.get(response.json()['data']['order_id']))
    data = row['payload_json']['data']
    assert data['direction'] == 'help' and data['visit'] is True
    assert row['payload_json']['calculator']['distance_pending'] is True


def test_corporate_has_no_calculator(client):
    response = send(client, payload(type='corporate', company='ООО Тест', fleet_size=12,
                    email='fleet@example.com', inn='1234567890'), endpoint='/api/corporate-orders')
    assert response.status_code == 201
    row = run(client, client.app.state.repo.get(response.json()['data']['order_id']))
    assert row['payload_json']['calculator'] is None
    assert row['payload_json']['data']['direction'] == 'corporate'


def test_visit_request_uses_dispatcher_flow_even_for_repair_service(client):
    response = send(client, payload(service='repair', visit=True, location={'address': 'М5, 300 км'}))
    assert response.status_code == 201
    assert response.json()['data']['direction'] == 'help'


def test_production_never_reports_success_without_persistent_db(tmp_path):
    settings = Settings(_env_file=None, app_env='production', database_path=str(tmp_path/'db'), worker_enabled=False)
    with TestClient(create_app(settings)) as client:
        assert send(client).status_code == 503


def test_database_failure_returns_error(client):
    client.app.state.repo.create = AsyncMock(side_effect=RuntimeError('database offline'))
    response = send(client)
    assert response.status_code == 503 and response.json()['success'] is False


def test_fake_image_rejected_and_request_origin_checked(client):
    assert send(client, photos=[('photos', ('fake.jpg', b'<script>bad</script>', 'image/jpeg'))]).status_code == 422
    assert client.post('/api/calculator', json={}, headers={'Origin': 'https://another.example'}).status_code == 403
    assert client.post('/api/orders', headers={'Content-Length': str(43*1024*1024)}).status_code == 413


def test_photo_upload_retry_and_delivery_failure_preserve_files(client):
    app = client.app
    settings = app.state.settings
    settings.telegram_bot_token, settings.telegram_chat_id = 'test-token', '-100123'
    settings.mail_transport, settings.resend_api_key = 'resend', 'test-email-key'
    settings.smtp_from, settings.manager_email = 'service@example.com', 'manager@example.com'
    original = app.state.photos.save
    app.state.photos.save = AsyncMock(side_effect=OSError('storage offline'))
    key = str(uuid.uuid4())
    assert send(client, key=key, photos=[('photos', ('../unsafe.png', photo(), 'image/png'))]).status_code == 503
    assert run(client, app.state.repo.claim()) == []
    app.state.photos.save = original
    response = send(client, key=key, photos=[('photos', ('../unsafe.png', photo(), 'image/png'))])
    assert response.status_code == 200
    order_id = response.json()['data']['order_id']
    folder = app.state.photos.folder(order_id)
    assert (folder/'photo-1.jpg').exists()
    calls = []
    fail_mail = True

    def transport(request):
        nonlocal fail_mail
        calls.append((request.url.host, request.url.path, request.content))
        if request.url.host == 'api.telegram.org':
            return httpx.Response(200, json={'ok': True, 'result': {'message_id': len(calls)}})
        return httpx.Response(503 if fail_mail else 200, json={'id': 'email-id'})

    async def cycle():
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as external:
            app.state.notifications.client = external
            await app.state.notifications.tick()
    run(client, cycle())
    jobs = run(client, app.state.repo.jobs(order_id))
    assert [j['status'] for j in jobs] == ['sent', 'failed']
    assert folder.exists()
    telegram_count = sum(host == 'api.telegram.org' for host, _, _ in calls)
    fail_mail = False
    run(client, app.state.repo.update_job(jobs[1]['id'], next_at=0))
    run(client, cycle())
    assert all(j['status'] == 'sent' for j in run(client, app.state.repo.jobs(order_id)))
    assert not folder.exists()
    assert sum(host == 'api.telegram.org' for host, _, _ in calls) == telegram_count
    email = json.loads([body for host, _, body in calls if host == 'api.resend.com'][-1])
    assert {a['filename'] for a in email['attachments']} == {'order.json', 'photo-1.jpg'}


def test_only_authorized_telegram_completion_updates_stats(client):
    response = send(client)
    order_id = response.json()['data']['order_id']
    app = client.app
    app.state.settings.telegram_chat_id = '-100123'
    app.state.settings.telegram_manager_ids = '42'
    job = run(client, app.state.repo.jobs(order_id))[0]
    run(client, app.state.repo.update_job(job['id'], progress={'message_ids': [100, 101]}))
    app.state.notifications.telegram_api = AsyncMock(return_value=True)
    update = {'callback_query': {'id': 'callback-id', 'data': 'done:'+order_id,
                'from': {'id': 99}, 'message': {'message_id': 101, 'chat': {'id': -100123}}}}
    run(client, app.state.notifications.complete(update))
    assert run(client, app.state.repo.get(order_id))['status'] == 'new'
    update['callback_query']['from']['id'] = 42
    run(client, app.state.notifications.complete(update))
    assert client.get('/api/stats').json()['data']['completed_orders'] == 1
    assert app.state.notifications.telegram_api.call_args.args[0] == 'deleteMessages'
