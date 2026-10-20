"""tax.gov.ir lookups without a captcha: activity codes (اینتاکد), property transaction values and the FAQ."""

from __future__ import annotations

import html as htmllib
import re
from typing import Annotated

from pydantic import Field

from . import http
from .registry import clip, tool

BASE = "https://tax.gov.ir"
FORM_TTL = 1800  # seconds a WebForms page (and its state) is reused for the next search
LIMIT_MAX = 20  # 20 activity-code rows stay under ~15 KB
FAQ_MAX = 40  # questions returned per FAQ search (about 250 bytes each)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_ROW = re.compile(r"<tr class='grid(?:Even|Odd)Class'>(.*?)</tr>", re.S)
_CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
_TITLE = re.compile(r'title="([^"]*)"')
_GEO = re.compile(r'geohead">(.*?)</div>\s*<div[^>]*geovalue">(.*?)</div>', re.S)
INTACODE_COLS = [
    "code",
    "title",
    "activity_type",
    "individual_business_type",
    "vat_status",
    "eight_groups",
    "business_group",
    "profit_ratio",
    "gross_profit_to_sales_ratio",
    "year",
    "taxpayer_type",
    "status",
]
GEO_KEYS = {
    "استان - شهرستان - شهر": "location",
    "اداره کل امور مالیاتی": "tax_directorate",
    "واحد مرتبط مالیاتی سنیم املاک": "tax_office_real_estate",
    "واحد مرتبط مالیاتی سنیم حقوقی": "tax_office_legal_persons",
    "واحد مرتبط مالیاتی سنیم حقیقی": "tax_office_natural_persons",
    "شماره بلوک بر اساس دفترچه ارزش معاملاتی ملک": "block",
    "شماره ردیف بر اساس دفترچه ارزش معاملاتی ملک": "row",
    "ارزش معاملاتی مسکونی": "value_residential",
    "ارزش معاملاتی اداری": "value_office",
    "ارزش معاملاتی تجاری": "value_commercial",
    "ارزش استیجاری مسکونی": "rent_residential",
    "ارزش استیجاری اداری": "rent_office",
    "ارزش استیجاری تجاری": "rent_commercial",
}


def _text(s: str) -> str:
    return _WS.sub(" ", htmllib.unescape(_TAG.sub(" ", s))).strip()


def _options(page: str, select_id: str) -> list[str]:
    """Option values of a <select> in document order."""
    m = re.search(rf'<select[^>]*id="{select_id}"[^>]*>(.*?)</select>', page, re.S)
    return re.findall(r'value="([^"]*)"', m[1]) if m else []


def _rial(v: str) -> int | str:
    """'89,900,000 ریال' to 89900000; other text (e.g. 'عدم وجود اطلاعات' = no data) is returned as is."""
    digits = v.replace("ریال", "").replace(",", "").strip()
    return int(digits) if digits.isdigit() else v


def parse_intacodes(page: str) -> list[dict]:
    out = []
    for row in _ROW.findall(page):
        cells = []
        for c in _CELL.findall(row):
            t = _TITLE.search(c)  # long values are cut in the cell and complete in the title attribute
            cells.append(_text(t[1] if t else c))
        if len(cells) == len(INTACODE_COLS):
            row = dict(zip(INTACODE_COLS, cells, strict=True))
            for k in ("profit_ratio", "gross_profit_to_sales_ratio"):
                row[k] = _num(row[k])
            row["year"] = _num(row["year"])
            row["eight_groups"] = clip(row["eight_groups"], n=80)
            out.append(row)
    return out


def _num(v: str) -> float | int | str:
    try:
        return int(v) if v.isdigit() else float(v)
    except ValueError:
        return v


def parse_geo(page: str) -> dict:
    out = {}
    for head, value in _GEO.findall(page):
        key = GEO_KEYS.get(_text(head))
        if key:
            v = _text(value).replace("اداره امورمالياتي", "اداره امور مالیاتی")
            out[key] = _rial(v) if key.startswith(("value_", "rent_")) else v
    return out


@tool("Search tax activity codes")
async def tx_activity_codes(
    query: Annotated[
        str,
        Field(
            min_length=2,
            description="Part of the activity title in Persian (e.g. 'نرم افزار', 'گندم'), or an activity code (digits).",
            examples=["نرم افزار"],
        ),
    ],
    year: Annotated[
        int | None,
        Field(description="Tax year (Jalali), e.g. 1404. Default: the latest year offered.", examples=[1404]),
    ] = None,
    commercial: Annotated[
        bool,
        Field(
            description="True: commercial activities (تجاری). False: non-commercial ones (غیرتجاری). The site has no 'both'.",
            examples=[True],
        ),
    ] = True,
    limit: Annotated[int, Field(ge=1, le=LIMIT_MAX, description=f"Max rows (1-{LIMIT_MAX}).", examples=[10])] = 10,
) -> dict:
    """Find tax activity codes (کد فعالیت / اینتاکد) with their VAT status and official profit ratios.

    Source: tax.gov.ir SearchIntaCode. Each row has the code, title, activity type (production/trade/services),
    vat_status (which VAT stage the activity falls in, or not subject), business group, profit_ratio (نسبت سود
    فعالیت, %) and gross_profit_to_sales_ratio (%), used for presumptive assessments. The ratios are not tax rates.
    """
    url = f"{BASE}/action/do/SearchIntaCode"
    page, state = await http.get_form(url)
    years = _options(page, "ddlYearForIntaCode")
    if not years:
        raise http.ApiError("tax.gov.ir activity-code form has no year list; the page layout may have changed.")
    y = str(year) if year else years[0]
    if y not in years:
        raise http.ApiError(f"Year {y} is not offered. Available: {', '.join(years)}.")
    q = query.strip()
    form = {
        **state,
        "__EVENTTARGET": "",
        "__EVENTARGUMENT": "",
        "txtIntaCode": q if q.isdigit() else "",
        "txtIntaCodeDescription": "" if q.isdigit() else q,
        "ddlYearForIntaCode": y,
        "ddlActionType": "0",
        "ddlIntaCodeVatEligibilityTypes": "0",
        "ddlIntaCodeTejari": "1" if commercial else "0",
        "ddlIntaCodeEnferadiTypes": "0",
        "ddlGroupOneForEditIntaCode": "0",
        "btnSearchIntaCode": "جستجو",
    }
    rows = parse_intacodes((await http.request("POST", url, data=form)).text)
    return {
        "query": q,
        "year": int(y),
        "commercial": commercial,
        "total": len(rows),
        "count": min(limit, len(rows)),
        "items": rows[:limit],
    }


@tool("Property transaction value")
async def tx_property_value(
    latitude: Annotated[
        float, Field(ge=25, le=40, description="Latitude of the property (WGS84).", examples=[35.6892])
    ],
    longitude: Annotated[
        float, Field(ge=44, le=64, description="Longitude of the property (WGS84).", examples=[51.389])
    ],
    year: Annotated[
        int | None,
        Field(description="Booklet year (Jalali), 1396 to the current year. Default: the latest.", examples=[1404]),
    ] = None,
) -> dict:
    """Return the official property transaction value (ارزش معاملاتی املاک) per square metre at a map point.

    Source: tax.gov.ir GetAddressGeoLocation. Gives the booklet block and row, residential/office/commercial
    values and rent values in rial per m² (text 'عدم وجود اطلاعات' when the booklet has none), and the tax offices
    for that address. The caller must supply coordinates; this server does not geocode addresses.
    """
    url = f"{BASE}/action/do/GetAddressGeoLocation/30/{latitude}/{longitude}"
    _, state = await http.get_form(url)
    form = {
        **state,
        "__EVENTTARGET": "",
        "__EVENTARGUMENT": "",
        "__LASTFOCUS": "",
        "TextboxLatitude": str(latitude),
        "TextboxLongitude": str(longitude),
        "ButtonSearchGeolocation": "استعلام",
    }
    page = (await http.request("POST", url, data=form)).text
    years = _options(page, "DDLLocationYears")
    if year and str(year) != (years[0] if years else ""):
        if str(year) not in years:
            raise http.ApiError(f"Year {year} is not offered for this point. Available: {', '.join(years) or 'none'}.")
        form = {
            **http.form_state(page),
            "__EVENTTARGET": "DDLLocationYears",
            "__EVENTARGUMENT": "",
            "__LASTFOCUS": "",
            "DDLLocationYears": str(year),
        }
        page = (await http.request("POST", url, data=form)).text
    result = parse_geo(page)
    if "block" not in result:
        raise http.ApiError("No transaction value found for that point (outside a covered city, or a layout change).")
    return {"latitude": latitude, "longitude": longitude, "year": year or (int(years[0]) if years else None), **result}


@tool("Search the tax FAQ")
async def tx_faq_search(
    query: Annotated[
        str,
        Field(min_length=2, description="Keywords in Persian, e.g. 'اظهارنامه', 'ماده 169'.", examples=["اظهارنامه"]),
    ],
) -> dict:
    """Search the tax administration's official FAQ (پرسش های متداول) and return matching questions with links.

    Source: tax.gov.ir SearchFAQ. Returns question titles and their page url; open the url for the answer.
    """
    r = await http.request("POST", f"{BASE}/handler/SearchFAQ.ashx", json={"q": query.strip(), "checkRequest": "1"})
    page = (r.json() or {}).get("contentHTML") or ""
    items = [
        {"question": clip(_text(t), n=300), "url": BASE + h.replace("/pages/action/faq/", "/action/do/faq/")}
        for h, t in re.findall(r"href=([^\s>]+)[^>]*>(.*?)</a>", page, re.S)
    ]
    return {"query": query, "total": len(items), "count": min(len(items), FAQ_MAX), "items": items[:FAQ_MAX]}
