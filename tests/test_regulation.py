from urllib.parse import parse_qs

import pytest
from conftest import fixture

from iran_tax_mcp import regulation

pytestmark = pytest.mark.anyio

SEARCH = "GET regulation.tax.gov.ir/lwse"
DOC = "GET regulation.tax.gov.ir/lwvi"


def query(req) -> dict[str, list[str]]:
    return parse_qs(req.url.query.decode())


def test_parse_search():
    total, items = regulation.parse_search(fixture("reg_search.html").decode())
    assert total == 7357 and len(items) == 2
    assert items[0] == {
        "id": "txs5000152382",
        "type": "regulation",
        "title": items[0]["title"],
        "number": "200/1405/59",
        "issuer": "رئیس کل سازمان امور مالیاتی کشور",
        "date": "1405/07/27",
        "status": "معتبر (دائمی)",
    }
    assert items[0]["title"].startswith("اصلاح بند (3) بخشنامه")


def test_parse_document_and_reading_order():
    d = regulation.parse_document(fixture("reg_law.html").decode())
    assert d["title"] == "قانون مالیات بر ارزش افزوده 1400/03/02" and d["kind"] == "قانون"
    assert d["issuer"] == "مجلس شورای اسلامی" and d["effective_date"] == "1400/10/10"
    assert d["pdf"].startswith("https://regulation.tax.gov.ir/uploads/")
    order = [r["ti"] for r in regulation.ordered(d["rows"])]
    assert order[0].startswith("قانون") and order[1].startswith("فصل اول") and order[2].startswith("فصل دوم")


def test_plain_text_and_norm():
    assert regulation._plain("<p>ماده 1-&nbsp;متن</p><p>تبصره</p>") == "ماده 1- متن\nتبصره"
    assert regulation._plain("-") == ""
    assert regulation._plain("فعالیت\u00adها") == "فعالیت\u200cها"
    assert regulation._norm("ماده ۱۶۹  مكرر") == "ماده 169 مکرر"


def test_chunks(monkeypatch):
    monkeypatch.setattr(regulation, "CHUNK", 10)
    assert regulation._chunks("aaaa\nbbbb\ncccccccccccccc\nd") == ["aaaa\nbbbb", "cccccccccccccc", "d"]


async def test_search_sends_type_fields_and_offset(client, routes):
    routes[SEARCH] = fixture("reg_search.html")
    d = (
        await client.call_tool("tx_regulations_search", {"query": "مالیات حقوق", "type": "regulation", "page": 3})
    ).structured_content
    assert d["total"] == 7357 and d["pages"] == 368 and d["count"] == 2
    q = query(routes.calls[0])
    assert q["act"] == ["mq"] and q["s281009734"] == ["مالیات حقوق"] and q["fr"] == ["40"]
    assert q["s281010109[]"] == [regulation.FIELD_TITLE, regulation.FIELD_TEXT]
    await client.call_tool("tx_regulations_search", {"query": "سفته", "title_only": True})
    assert query(routes.calls[1])["s281010109[]"] == [regulation.FIELD_TITLE]


async def test_text_whole_and_one_article(client, routes):
    routes[DOC] = fixture("reg_article.html")
    d = (await client.call_tool("tx_regulation_text", {"id": "txs5000060480", "type": "law"})).structured_content
    assert d["parts"] == 1 and d["text"].startswith("ماده 2-") and "تبصره 2-" in d["text"]
    assert query(routes.calls[0]) == {"lid": ["txs5000060480"], "ty": ["qh"]}
    d = (
        await client.call_tool("tx_regulation_text", {"id": "txs5000060480", "type": "law", "article": "تبصره ۱"})
    ).structured_content
    assert d["text"].startswith("تبصره 1-") and "تبصره 2" not in d["text"]
    assert len(routes.calls) == 1  # the document is cached


async def test_unknown_article_and_bad_part(client, routes):
    routes[DOC] = fixture("reg_circular.html")
    r = await client.call_tool(
        "tx_regulation_text", {"id": "txs5000152382", "type": "regulation", "article": "ماده 99"}
    )
    assert r.is_error and "No heading" in r.content[0].text
    r = await client.call_tool("tx_regulation_text", {"id": "txs5000152382", "type": "regulation", "part": 5})
    assert r.is_error and "only 1 part" in r.content[0].text


async def test_page_without_text_is_an_error(client, routes):
    routes[DOC] = b"<html><title>x</title></html>"
    r = await client.call_tool("tx_regulation_text", {"id": "txs1", "type": "law"})
    assert r.is_error and "without document text" in r.content[0].text


async def test_bad_id_is_rejected(client):
    r = await client.call_tool("tx_regulation_text", {"id": "../etc", "type": "law"})
    assert r.is_error
