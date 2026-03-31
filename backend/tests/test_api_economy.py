import pytest

from app.services.economy_analyzer import EconomyAnalyzer


@pytest.mark.asyncio
async def test_get_economy_overview_success(client, sample_data):
    response = await client.get("/api/v1/economy/overview", params={"period": "202503"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["period"] == "202503"
    assert payload["total_regions"] >= 2
    assert "regions" in payload


@pytest.mark.asyncio
async def test_get_region_economy_success(client, sample_data):
    response = await client.get("/api/v1/economy/11110", params={"period": "202503"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["region_code"] == "11110"
    assert payload["signal"] in ["호황", "보통", "침체"]


@pytest.mark.asyncio
async def test_get_region_economy_not_found(monkeypatch, client):
    async def _raise_not_found(self, region: str, period: str | None = None):
        raise ValueError("region not found")

    monkeypatch.setattr(EconomyAnalyzer, "analyze", _raise_not_found)

    response = await client.get("/api/v1/economy/99999")

    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "http_error"
