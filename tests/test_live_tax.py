import pytest

pytestmark = [pytest.mark.anyio, pytest.mark.live]


async def call(client, name, args):
    result = await client.call_tool(name, args)
    assert not result.is_error, result.content[0].text
    return result.structured_content


async def test_goods_search(client):
    data = await call(client, "tx_goods_search", {"query": "لپ تاپ", "kind": "goods", "limit": 5})
    assert data["total"] > 100 and data["items"][0]["id"].isdigit() and len(data["items"][0]["id"]) == 13
    assert data["items"][0]["vat_percent"] in (9.0, 10.0)


async def test_activity_codes(client):
    data = await call(client, "tx_activity_codes", {"query": "نرم افزار", "limit": 5})
    assert data["items"] and data["items"][0]["code"].isdigit() and data["items"][0]["vat_status"]


async def test_property_value(client):
    data = await call(client, "tx_property_value", {"latitude": 35.6892, "longitude": 51.389})
    assert data["block"] and isinstance(data["value_residential"], int)


async def test_faq_search(client):
    data = await call(client, "tx_faq_search", {"query": "اظهارنامه"})
    assert data["count"] > 0 and data["items"][0]["url"].startswith("https://tax.gov.ir/")


async def test_regulations_search_and_text(client):
    data = await call(client, "tx_regulations_search", {"query": "سفته", "title_only": True})
    assert 0 < data["total"] < 100  # the query filters (an ignored query returns all ~7000 documents)
    law = await call(client, "tx_regulation_text", {"id": "txs5000060480", "type": "law", "article": "ماده 2"})
    assert law["text"].startswith("ماده 2") and law["kind"] == "قانون"
