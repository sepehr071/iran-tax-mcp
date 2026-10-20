"""Goods and service IDs (شناسه کالا و خدمات) for e-invoices, from stuffid.tax.gov.ir, with their VAT rate."""

from __future__ import annotations

import csv
import io
import zipfile
from datetime import date
from typing import Annotated, Literal

from pydantic import Field

from . import http
from .registry import clip, tool

GATEWAY = "https://stuffid.tax.gov.ir/portal-gateway"
EXPORT_TTL = 3600  # seconds; the ID list changes a few times a day at most
LIMIT_MAX = 20  # 20 rows with descriptions cut at 200 characters stay under ~15 KB
QUERY = (
    "query($i: GetInformationWithIDFilterServiceInputDto32973QueryInput){ GetInformationWithIDFilter(input:$i)"
    "{ statusCode message data { fileName } subStatuses { message } } }"
)
KINDS = {"goods": 0, "service": 1, "all": None}


def jalali(d: date) -> str:
    """Gregorian date to Jalali 'YYYY-MM-DD' (the format of the ID list's dates)."""
    gy, gm, gd = d.year, d.month, d.day
    days = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    n = 355666 + 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400 + gd + days[gm - 1]
    jy = -1595 + 33 * (n // 12053)
    n %= 12053
    jy += 4 * (n // 1461)
    n %= 1461
    if n > 365:
        jy += (n - 1) // 365
        n = (n - 1) % 365
    jm, jd = (1 + n // 31, 1 + n % 31) if n < 186 else (7 + (n - 186) // 30, 1 + (n - 186) % 30)
    return f"{jy:04d}-{jm:02d}-{jd:02d}"


async def _export(code: str, title: str, kind: str) -> list[dict[str, str]]:
    """Ask stuffid to build a CSV export for the filter, download the zip and return its rows (cached EXPORT_TTL)."""

    async def make() -> list[dict[str, str]]:
        body = {
            "query": QUERY,
            "variables": {"i": {"isService": KINDS[kind], "exportType": 0, "code": code, "title": title}},
        }
        r = (await http.request("POST", f"{GATEWAY}/StuffRate/gs/graphql", json=body)).json()
        res = (r.get("data") or {}).get("GetInformationWithIDFilter") or {}
        name = (res.get("data") or {}).get("fileName")
        if not name:
            msg = " ".join(s.get("message") or "" for s in res.get("subStatuses") or []) or res.get("message") or ""
            if res.get("statusCode") in (200, 402):  # 402 = no row matches
                return []
            raise http.ApiError(f"stuffid.tax.gov.ir could not build the ID list: {msg or r.get('errors')}")
        z = (await http.request("GET", f"{GATEWAY}/upload/gs/api/v1/exportguest/download/{name}")).content
        try:
            with zipfile.ZipFile(io.BytesIO(z)) as f:
                text = f.read(f.namelist()[0]).decode("utf-8-sig")
        except (zipfile.BadZipFile, IndexError) as e:
            raise http.ApiError("stuffid.tax.gov.ir sent a broken export file; try again in a minute.") from e
        return list(csv.DictReader(io.StringIO(text)))

    return await http.cached(("goods", code, title, kind), EXPORT_TTL, make)


def _row(r: dict[str, str], today: str) -> dict:
    exp = r.get("ExpirationDate") or None
    return {
        "id": r.get("ID"),
        "description": clip(r.get("DescriptionOfID"), n=200),
        "vat_percent": float(r["Vat"]) if (r.get("Vat") or "").replace(".", "", 1).isdigit() else r.get("Vat") or None,
        "taxable": r.get("Taxable") or None,
        "type": r.get("Type") or None,
        "start_date": r.get("RunDate") or None,
        "expiration_date": exp,
        "expired": bool(exp and exp < today) or None,
        "pricing": r.get("PricingDescription") or None,
    }


def _rank(r: dict[str, str], today: str, q: str) -> tuple:
    """Active before expired, general (عمومی) before specific IDs, descriptions starting with the query first, then
    the shortest (most generic) description."""
    exp = r.get("ExpirationDate") or ""
    d = r.get("DescriptionOfID") or ""
    return (bool(exp and exp < today), "عمومی" not in (r.get("Type") or ""), not d.startswith(q), len(d))


@tool("Search goods and service IDs")
async def tx_goods_search(
    query: Annotated[
        str,
        Field(
            min_length=2,
            description="Part of the goods/service description in Persian, matched as one phrase (e.g. 'لپ تاپ', 'خدمات حسابداری'), or a 13-digit ID.",
            examples=["لپ تاپ"],
        ),
    ],
    kind: Annotated[
        Literal["goods", "service", "all"], Field(description="Goods IDs, service IDs or both.", examples=["goods"])
    ] = "all",
    general_only: Annotated[
        bool,
        Field(description="Only general IDs (شناسه عمومی), the ones most sellers put on e-invoices.", examples=[True]),
    ] = False,
    limit: Annotated[int, Field(ge=1, le=LIMIT_MAX, description=f"Max rows (1-{LIMIT_MAX}).", examples=[10])] = 10,
) -> dict:
    """Find e-invoice goods/service IDs (شناسه کالا و خدمات) and their VAT rate by description or ID.

    Source: the tax administration's ID system stuffid.tax.gov.ir. Active general IDs come first. Each row has the
    13-digit id, description, vat_percent, type (general/specific, domestic/imported) and dates; `expired: true`
    means the ID can no longer be used. The first search for a phrase takes 15-30 s (the site builds a file);
    repeats are cached for an hour. `total` counts every match, not only the rows returned.
    """
    q = query.strip()
    code, title = (q, "") if q.isdigit() else ("", q)
    rows = await _export(code, title, kind)
    if general_only:
        rows = [r for r in rows if "عمومی" in (r.get("Type") or "")]
    today = jalali(date.today())
    top = sorted(rows, key=lambda r: _rank(r, today, title))[:limit]
    return {"query": q, "kind": kind, "total": len(rows), "count": len(top), "items": [_row(r, today) for r in top]}
