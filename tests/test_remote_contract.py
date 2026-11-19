import asyncio
import json
import httpx
from app.config import Settings
from app.repository import Repository
from app.services.photos import Photos


def test_remote_adapter_uses_server_credentials_and_private_storage(tmp_path):
    async def execute():
        settings = Settings(_env_file=None, supabase_url='https://test.supabase.co', supabase_key='server-only')
        order_id = 'GSS-2026-ABCDEF123456'
        payload = {'id': order_id, 'photos': []}
        row = {'id': order_id, 'payload_json': payload, 'status': 'new'}
        requests = []
        def route(request):
            requests.append(request)
            assert request.headers['apikey'] == 'server-only'
            if request.url.path.endswith('/rpc/create_order'):
                assert json.loads(request.content)['p_payload'] == payload
                return httpx.Response(200, json={'order': row, 'created': True})
            if request.method == 'GET' and '/storage/' in request.url.path:
                return httpx.Response(200, content=b'image')
            if request.url.path.endswith('/rpc/claim_notifications'):
                return httpx.Response(200, json=[])
            if request.url.path.endswith('/rpc/cleanup_candidates'):
                return httpx.Response(200, json=[row])
            return httpx.Response(200, json=[])
        async with httpx.AsyncClient(transport=httpx.MockTransport(route)) as client:
            repo = Repository(settings, client)
            saved, created = await repo.create(payload, 'dc97b159-7bb1-4112-b58e-4165c0ba702f', 'hash', ['telegram','email'])
            assert created and saved['id'] == order_id
            assert await repo.claim() == []
            assert (await repo.cleanup_candidates())[0]['id'] == order_id
            photos = Photos(settings, client)
            photos.root = tmp_path / 'photos'
            manifest = photos.manifest(order_id, [b'image'])
            await photos.save(order_id, manifest, [b'image'])
            (photos.folder(order_id) / 'photo-1.jpg').unlink()
            assert await photos.read(manifest[0]) == b'image'
            await photos.delete({'id': order_id, 'payload_json': {'photos': manifest}})
            deletion = requests[-1]
            assert deletion.method == 'DELETE'
            assert json.loads(deletion.content) == {'prefixes': [order_id+'/photo-1.jpg']}
    asyncio.run(execute())
