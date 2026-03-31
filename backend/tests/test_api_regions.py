import pytest


@pytest.mark.asyncio
async def test_get_regions(client):
    response = await client.get("/api/v1/regions")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 9


@pytest.mark.asyncio
async def test_get_region_listings_pagination_and_filter(client, sample_data):
    response = await client.get(
        "/api/v1/regions/11110/listings",
        params={"page": 1, "size": 10, "property_type": "아파트"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 1
    assert payload["size"] == 10
    assert payload["total"] == 1
    assert len(payload["items"]) == 1
    assert payload["items"][0]["property_type"] == "아파트"


@pytest.mark.asyncio
async def test_get_region_listings_invalid_price_range(client):
    response = await client.get(
        "/api/v1/regions/11110/listings",
        params={"min_price": 100, "max_price": 10},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "http_error"


@pytest.mark.asyncio
async def test_get_region_prices_aggregation(client, sample_data):
    response = await client.get("/api/v1/regions/11110/prices")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 2
    assert payload[0]["period"] == "2025-01"
    assert payload[0]["transaction_count"] == 2
