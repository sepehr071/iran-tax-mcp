import io
import json
import zipfile
from datetime import date

import httpx
import pytest

from iran_tax_mcp import goods

pytestmark = pytest.mark.anyio

GQL = "POST stuffid.tax.gov.ir/portal-gateway/StuffRate/gs/graphql"
DL = "stuffid.tax.gov.ir/portal-gateway/upload/gs/api/v1/exportguest/download/f.zip"
HEADER = "ID,DescriptionOfID,Vat,Taxable,RunDate,ExpirationDate,CreateDate,LastEditDate,Type,PricingDescription\n"
ROWS = [
    "2800017022259,لپ تاپ، 15.6 in، برند ASUS,10,مشمول,1405-07-07,,1405-07-07,1405-07-07,شناسه اختصاصی وارداتی,",
    "2710000101901,صفحه خنک کننده لپ تاپ,9,مشمول,1402-01-01,1402-12-29,1402-01-01,1402-01-01,شناسه عمومی وارداتی,",
    "2720000068364,کیف لپ تاپ,10,مشمول,1403-01-01,,1403-01-01,1403-01-01,شناسه عمومی تولید داخل,",
    "2710000101482,لپ تاپ (نوت بوک),10,مشمول,1403-01-01,,1403-01-01,1403-01-01,شناسه عمومی وارداتی,",
]


def export_zip(rows=ROWS) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("f.csv", ("\ufeff" + HEADER + "\n".join(rows) + "\n").encode())
    return buf.getvalue()


def gql_answer(file_name="f.zip", status=200):
    body = {
        "data": {
            "GetInformationWithIDFilter": {
                "statusCode": status,
                "message": "Success",
                "data": {"fileName": file_name},
                "subStatuses": [],
            }
        }
    }
    return lambda req: httpx.Response(200, json=body)


def test_jalali():
    assert goods.jalali(date(2026, 10, 20)) == "1405-07-28"
    assert goods.jalali(date(2026, 3, 21)) == "1405-01-01"
    assert goods.jalali(date(2025, 3, 20)) == "1403-12-30"  # 1403 is a leap year


async def test_search_ranks_active_general_and_prefix_first(client, routes):
    routes[GQL] = gql_answer()
    routes[DL] = export_zip()
    d = (await client.call_tool("tx_goods_search", {"query": "لپ تاپ", "kind": "goods"})).structured_content
    ids = [i["id"] for i in d["items"]]
    # general+prefix, general, specific, then the expired general ID last
    assert ids == ["2710000101482", "2720000068364", "2800017022259", "2710000101901"]
    assert d["total"] == 4 and d["items"][0]["vat_percent"] == 10.0
    assert d["items"][-1]["expired"] is True and "expired" not in d["items"][0]
    sent = json.loads(routes.calls[0].content)["variables"]["i"]
    assert sent == {"isService": 0, "exportType": 0, "code": "", "title": "لپ تاپ"}


async def test_search_by_id_general_only_and_cache(client, routes):
    routes[GQL] = gql_answer()
    routes[DL] = export_zip()
    d = (await client.call_tool("tx_goods_search", {"query": "2710000101482", "general_only": True})).structured_content
    assert d["total"] == 3
    assert json.loads(routes.calls[0].content)["variables"]["i"]["code"] == "2710000101482"
    await client.call_tool("tx_goods_search", {"query": "2710000101482", "general_only": True})
    assert len(routes.calls) == 2  # second call served from the cache


async def test_no_match_returns_empty(client, routes):
    routes[GQL] = gql_answer(file_name=None, status=402)
    d = (await client.call_tool("tx_goods_search", {"query": "چیزی که نیست"})).structured_content
    assert d["total"] == 0 and d["items"] == []


async def test_broken_zip_is_an_error(client, routes):
    routes[GQL] = gql_answer()
    routes[DL] = b"<html>not a zip</html>"
    r = await client.call_tool("tx_goods_search", {"query": "لپ تاپ"})
    assert r.is_error and "broken export" in r.content[0].text


async def test_max_limit_reply_stays_under_15kb(client, routes):
    long = "،".join(["لپ تاپ با مشخصات بسیار طولانی"] * 20)
    routes[GQL] = gql_answer()
    routes[DL] = export_zip(
        [f"28000{i:08d},{long},10,مشمول,1405-01-01,,1405-01-01,1405-01-01,شناسه اختصاصی وارداتی," for i in range(200)]
    )
    r = await client.call_tool("tx_goods_search", {"query": "لپ تاپ", "limit": goods.LIMIT_MAX})
    assert r.structured_content["count"] == goods.LIMIT_MAX and len(r.content[0].text.encode()) < 15_000
