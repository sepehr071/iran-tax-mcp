"""Tax laws, regulations, circulars, rulings and opinions from regulation.tax.gov.ir (سامانه جامع مقررات مالیاتی)."""

from __future__ import annotations

import html as htmllib
import json
import re
from typing import Annotated, Literal

from pydantic import Field

from . import http
from .registry import clip, tool

BASE = "https://regulation.tax.gov.ir"
PAGE_SIZE = 20  # fixed by the site
CHUNK = 6000  # characters per text part; Persian is 2 bytes per character, so a part stays under ~15 KB
DOC_TTL = 3600
TYPES = {
    "all": "all",
    "law": "qh",
    "regulation": "mq",
    "ruling": "ry",
    "opinion": "nz",
    "correspondence": "mk",
    "glossary": "kw",
}
TY_NAMES = {v: k for k, v in TYPES.items()}
FIELD_TITLE, FIELD_TEXT = "s281010107", "s281010108"
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t\r\f\v\u00a0\u200e\u200f]+")
_CARD = re.compile(r'data-tooltip="([^"]*)">.*?href="lwvi\?lid=(\w+)&ty=(\w+)', re.S)
_META = re.compile(r'<p class="">\s*([^<:]{2,30}):</p>\s*<p class="">([^<]*)</p>')
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
META_KEYS = {
    "نوع": "kind",
    "شماره": "number",
    "تاریخ صدور": "issue_date",
    "تاریخ تصویب": "approval_date",
    "مرجع تصویب": "issuer",
    "مرجع صدور": "issuer",
    "تاریخ لازم الاجرا": "effective_date",
    "وضعیت": "status",
}

DocType = Annotated[
    Literal["law", "regulation", "ruling", "opinion", "correspondence", "glossary"],
    Field(description="Document type, as returned by tx_regulations_search.", examples=["law"]),
]


def _norm(s: str) -> str:
    """Persian/Arabic digits to ASCII, Arabic ي/ك to Persian, ZWNJ to space, collapsed spaces."""
    s = s.translate(_DIGITS).replace("ي", "ی").replace("ك", "ک").replace("\u200c", " ")
    return _WS.sub(" ", s).strip()


def _plain(fragment: str) -> str:
    """HTML of one row to plain text: block ends become newlines, other tags vanish."""
    s = re.sub(r"(?i)<br\s*/?>|</(p|div|li|tr|h\d)>", "\n", fragment or "")
    s = htmllib.unescape(_TAG.sub("", s)).replace("\u00ad", "\u200c")  # old texts use soft hyphens as ZWNJ
    lines = (_WS.sub(" ", x).strip() for x in s.split("\n"))
    return "\n".join(x for x in lines if x and x != "-")  # a bare "-" is the empty text of a document's root row


def parse_search(page: str) -> tuple[int, list[dict]]:
    m = re.search(r'<b class="px-2" >(\d+)</b>', page)
    total = int(m[1]) if m else 0
    items = []
    for card in page.split("mt-3 sm:mt-5 rounded-lg border")[1:]:
        c = _CARD.search(card)
        if not c:
            continue
        flat = _WS.sub(" ", htmllib.unescape(_TAG.sub(" | ", re.sub(r"<svg.*?</svg>", "", card, flags=re.S))))
        meta = dict(re.findall(r"(شماره|مرجع صدور|تاریخ صدور|تاریخ تصویب|وضعیت)\s*:[\s|]*([^|]+?)\s*\|", flat))
        items.append(
            {
                "id": c[2],
                "type": TY_NAMES.get(c[3], c[3]),
                "title": clip(htmllib.unescape(c[1]).strip(), n=250),
                "number": meta.get("شماره"),
                "issuer": meta.get("مرجع صدور"),
                "date": meta.get("تاریخ صدور") or meta.get("تاریخ تصویب"),
                "status": meta.get("وضعیت"),
            }
        )
    return total, items


def parse_document(page: str) -> dict:
    """Title, metadata, PDF link and the rows (`chlist`) of a document page."""
    title = re.search(r"<title>([^<]*)", page)
    meta = {}
    for k, v in _META.findall(page):
        if (key := META_KEYS.get(k.strip())) and v.strip():
            meta.setdefault(key, v.strip())
    pdf = re.search(r'href="(/uploads/[^"]+\.pdf)"', page)
    i = page.find("let chlist = ")
    if i < 0:
        raise http.ApiError("regulation.tax.gov.ir returned a page without document text; the id or type may be wrong.")
    rows, _ = json.JSONDecoder().raw_decode(page, i + len("let chlist = "))
    return {
        "title": htmllib.unescape(title[1]).strip() if title else None,
        **meta,
        "pdf": BASE + pdf[1] if pdf else None,
        "rows": rows,
    }


def ordered(rows: list[dict], root: str | None = None) -> list[dict]:
    """Rows in reading order: depth-first from the top rows (or from `root`), children sorted by `ord`."""
    ids = {r.get("tk") for r in rows}
    kids: dict[str | None, list[dict]] = {}
    for r in rows:
        kids.setdefault(r.get("pcode") if r.get("pcode") in ids else None, []).append(r)
    out: list[dict] = []

    def walk(parent: str | None) -> None:
        for r in sorted(kids.get(parent, []), key=lambda x: float(x.get("ord") or 0)):
            out.append(r)
            walk(r.get("tk"))

    if root is None:
        walk(None)
    else:
        top = next(r for r in rows if r.get("tk") == root)
        out.append(top)
        walk(root)
    return out


def _chunks(text: str) -> list[str]:
    """Split on line boundaries into parts of at most CHUNK characters (a longer line stays whole)."""
    out = [""]
    for line in text.split("\n"):
        if out[-1] and len(out[-1]) + len(line) + 1 > CHUNK:
            out.append("")
        out[-1] = f"{out[-1]}\n{line}" if out[-1] else line
    return out


@tool("Search tax regulations")
async def tx_regulations_search(
    query: Annotated[
        str,
        Field(
            min_length=2,
            description="Words in Persian, e.g. 'ماده 169 مکرر', 'مالیات حقوق', 'سفته بازی', or a circular number like '200/1405/59'.",
            examples=["مالیات حقوق"],
        ),
    ],
    type: Annotated[
        Literal["all", "law", "regulation", "ruling", "opinion", "correspondence", "glossary"],
        Field(
            description="law = قوانین, regulation = مقررات/بخشنامه/دستورالعمل/آیین نامه, ruling = آرای دیوان و هیئت ها, "
            "opinion = نظریه ها, correspondence = مکاتبات, glossary = واژگان.",
            examples=["regulation"],
        ),
    ] = "all",
    title_only: Annotated[
        bool, Field(description="Match the title (and number) only, not the full text.", examples=[False])
    ] = False,
    page: Annotated[int, Field(ge=1, description="Result page, 20 per page, newest first.", examples=[1])] = 1,
) -> dict:
    """Search the official tax regulation database (laws, circulars, rulings, opinions), newest first.

    Source: regulation.tax.gov.ir (سامانه جامع مقررات مالیاتی). Each item has id and type (pass both to
    tx_regulation_text), title, number, issuer, date (Jalali) and status (معتبر = in force, غیر معتبر = not).
    """
    params: list[tuple[str, str]] = [
        ("act", TYPES[type]),
        ("s281009734", query.strip()),
        ("s281010109[]", FIELD_TITLE),
        ("fr", str((page - 1) * PAGE_SIZE)),
        ("sr", "desk"),
    ]
    if not title_only:
        params.insert(3, ("s281010109[]", FIELD_TEXT))
    total, items = parse_search((await http.request("GET", f"{BASE}/lwse", params=params)).text)
    return {
        "query": query,
        "type": type,
        "total": total,
        "page": page,
        "pages": -(-total // PAGE_SIZE),
        "count": len(items),
        "items": items,
    }


@tool("Read a tax regulation")
async def tx_regulation_text(
    id: Annotated[
        str,
        Field(
            pattern=r"^txs\d+$",
            description="Document id from tx_regulations_search, e.g. txs5000060480 (VAT law) or txs5000060569 (direct tax law).",
            examples=["txs5000060480"],
        ),
    ],
    type: DocType,
    article: Annotated[
        str,
        Field(
            description="Optional heading to read only that part, e.g. 'ماده 2', 'ماده 169 مکرر', 'فصل سوم'. Empty = whole document.",
            examples=["ماده 2"],
        ),
    ] = "",
    part: Annotated[
        int,
        Field(ge=1, description=f"Part number for long texts ({CHUNK} characters each); see `parts`.", examples=[1]),
    ] = 1,
) -> dict:
    """Return the full text of one tax law, circular, ruling or opinion, or just one article of it.

    Source: regulation.tax.gov.ir. Gives title, kind, number, dates, issuer, the official PDF link and the text in
    reading order with each article heading on its own line. Long laws come in parts: `parts` > 1 means call again
    with part=2, 3, ... For one article of a big law (the direct tax law is ~300 articles) pass `article`.
    """
    ty = TYPES[type]

    async def load() -> dict:
        page = (await http.request("GET", f"{BASE}/lwvi", params={"lid": id, "ty": ty})).text
        return parse_document(page)

    doc = await http.cached(("reg", id, ty), DOC_TTL, load)
    rows = doc["rows"]
    if article.strip():
        want = _norm(article)
        hit = next((r for r in rows if _norm(r.get("ti") or "") == want), None) or next(
            (r for r in rows if _norm(r.get("ti") or "").startswith(want + " ")), None
        )
        if hit is None:
            raise http.ApiError(
                f"No heading '{article}' in this document. Read it without `article` to see its headings."
            )
        rows = ordered(rows, hit.get("tk"))
    else:
        rows = ordered(rows)
    text = "\n".join(t for r in rows if (t := _plain(r.get("s80512493") or "")))
    parts = _chunks(text)
    if part > len(parts):
        raise http.ApiError(f"This text has only {len(parts)} part(s).")
    meta = {k: v for k, v in doc.items() if k != "rows"}
    return {
        "id": id,
        "type": type,
        **meta,
        "article": article or None,
        "part": part,
        "parts": len(parts),
        "text": parts[part - 1],
    }
