import asyncio
import httpx
from app.config import Settings
from app.schemas import Calculation
from app.services.calculator import Calculator


def calculate(settings, data, transport=None):
    async def execute():
        async with httpx.AsyncClient(transport=transport) as client:
            return await Calculator(settings, client).calculate(Calculation(**data))
    return asyncio.run(execute())


def test_real_road_distance_and_pricing():
    settings = Settings(_env_file=None, company_latitude=55, company_longitude=37, yandex_routing_api_key='test')
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={'rows':[{'elements':[{'status':'OK','distance':{'value':100000}}]}]}))
    result = calculate(settings, dict(service='help', location={'latitude':56,'longitude':38}), transport)
    assert result['distance_source'] == 'road' and result['distance_km'] == 100
    assert result['visit_from'] == 16400
    assert result['total_from'] == 26400


def test_route_failure_has_explicit_estimate_and_no_service_area_cutoff():
    settings = Settings(_env_file=None, company_latitude=55, company_longitude=37, yandex_routing_api_key='test')
    result = calculate(settings, dict(service='help',location={'latitude':20,'longitude':100}), httpx.MockTransport(lambda _: httpx.Response(503)))
    assert result['distance_source'] == 'approximate'
    assert result['individual'] is True and result['total_from'] is None


def test_missing_center_does_not_claim_known_distance():
    result = calculate(Settings(_env_file=None), dict(service='help', location={'latitude':55,'longitude':37}))
    assert result['distance_pending'] is True
    assert result['distance_km'] is None
