from urllib.parse import parse_qs

import httpx
import pytest
from conftest import fixture

from iran_tax_mcp import taxgov

pytestmark = pytest.mark.anyio

INTA = "tax.gov.ir/action/do/SearchIntaCode"
GEO = "tax.gov.ir/action/do/GetAddressGeoLocation/30/35.6892/51.389"


def form(req) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(req.content.decode(), keep_blank_values=True).items()}


def test_parse_intacodes():
    rows = taxgov.parse_intacodes(fixture("intacode.html").decode())
    assert len(rows) == 17
    r = rows[0]
    assert r["code"] == "1020180" and r["vat_status"] == "مشمول مرحله دوم" and r["business_group"] == "صنعت نان"
    assert r["profit_ratio"] == 1.6 and r["gross_profit_to_sales_ratio"] == 2.08 and r["year"] == 1404
    assert (
        r["status"] == "فعال" and r["eight_groups"].endswith("...[cut]") and len(r["eight_groups"]) == 88
    )  # 80 + the 8-char marker


def test_parse_geo():
    g = taxgov.parse_geo(fixture("geo.html").decode())
    assert g["block"] == "11" and g["row"] == "3"
    assert g["value_residential"] == 89_900_000 and g["value_commercial"] == 228_200_000
    assert g["rent_office"] == "عدم وجود اطلاعات"
    assert "اداره امور مالیاتی 3422" in g["tax_office_legal_persons"]
    assert taxgov.parse_geo(fixture("geo_1402.html").decode())["rent_residential"] == 956_250


async def test_activity_codes_posts_form_state_and_year(client, routes):
    page = fixture("intacode.html")
    routes[f"GET {INTA}"] = page
    routes[f"POST {INTA}"] = page
    r = await client.call_tool("tx_activity_codes", {"query": "گندم", "limit": 2})
    d = r.structured_content
    assert d["year"] == 1404 and d["total"] == 17 and d["count"] == 2 and d["commercial"] is True
    sent = form(routes.calls[-1])
    assert sent["txtIntaCodeDescription"] == "گندم" and sent["txtIntaCode"] == ""
    assert sent["ddlYearForIntaCode"] == "1404" and sent["ddlIntaCodeTejari"] == "1"
    assert sent["__VIEWSTATE"] and sent["__EVENTVALIDATION"]


async def test_activity_codes_by_code_and_bad_year(client, routes):
    routes[INTA] = fixture("intacode.html")
    await client.call_tool("tx_activity_codes", {"query": "1020180", "commercial": False})
    sent = form(routes.calls[-1])
    assert (
        sent["txtIntaCode"] == "1020180" and sent["txtIntaCodeDescription"] == "" and sent["ddlIntaCodeTejari"] == "0"
    )
    r = await client.call_tool("tx_activity_codes", {"query": "گندم", "year": 1390})
    assert r.is_error and "not offered" in r.content[0].text


async def test_property_value_default_year(client, routes):
    routes[f"GET {GEO}"] = fixture("geo.html")
    routes[f"POST {GEO}"] = fixture("geo.html")
    d = (await client.call_tool("tx_property_value", {"latitude": 35.6892, "longitude": 51.389})).structured_content
    assert d["year"] == 1405 and d["value_office"] == 138_300_000
    sent = form(routes.calls[-1])
    assert sent["TextboxLatitude"] == "35.6892" and sent["ButtonSearchGeolocation"]


async def test_property_value_other_year_posts_back_the_dropdown(client, routes):
    routes[f"GET {GEO}"] = fixture("geo.html")
    routes[f"POST {GEO}"] = lambda req: httpx.Response(
        200, content=fixture("geo_1402.html") if b"DDLLocationYears=1402" in req.content else fixture("geo.html")
    )
    d = (
        await client.call_tool("tx_property_value", {"latitude": 35.6892, "longitude": 51.389, "year": 1402})
    ).structured_content
    assert d["year"] == 1402 and d["row"] == "1" and d["value_residential"] == 20_600_000
    assert form(routes.calls[-1])["__EVENTTARGET"] == "DDLLocationYears"


async def test_property_value_without_result_is_an_error(client, routes):
    routes[GEO] = b'<input type="hidden" id="__VIEWSTATE" value="x" /><select id="DDLLocationYears"></select>'
    r = await client.call_tool("tx_property_value", {"latitude": 35.6892, "longitude": 51.389})
    assert r.is_error and "No transaction value" in r.content[0].text


async def test_faq_search(client, routes):
    routes["POST tax.gov.ir/handler/SearchFAQ.ashx"] = fixture("faq.json")
    d = (await client.call_tool("tx_faq_search", {"query": "صورتحساب"})).structured_content
    assert d["count"] == 1 and d["items"][0]["url"] == "https://tax.gov.ir/action/do/faq/47/2253"
    assert d["items"][0]["question"].startswith("در چه صورتی")


async def test_missing_form_state_is_a_clear_error(client, routes):
    routes[INTA] = b"<html>maintenance</html>"
    r = await client.call_tool("tx_activity_codes", {"query": "گندم"})
    assert r.is_error and "form state" in r.content[0].text


async def test_max_limit_activity_codes_stay_under_15kb(client, routes):
    row = fixture("intacode.html").decode()
    body = row.split("<tr class='gridEvenClass'>")[1].split("</tr>")[0]
    routes[INTA] = row.replace(
        "</table></span>", f"<tr class='gridOddClass'>{body}</tr>" * 40 + "</table></span>", 1
    ).encode()
    r = await client.call_tool("tx_activity_codes", {"query": "گندم", "limit": taxgov.LIMIT_MAX})
    assert r.structured_content["count"] == taxgov.LIMIT_MAX and len(r.content[0].text.encode()) < 15_000
