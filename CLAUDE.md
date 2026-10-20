# iran-tax-mcp

Unofficial, read-only MCP server over public services of the Iranian National Tax Administration: tax.gov.ir,
stuffid.tax.gov.ir (goods/service IDs) and regulation.tax.gov.ir (tax regulation database). Copies the layout of
`../iran-news-mcp`; keep them in step. Not yet published (no commit, tag or PyPI release). API maps: `../tax-gov/`,
`../moadian/` (stuffid + e-invoice API), `../tax-regulation/`, `../intamedia/` (not used by the server yet).

## Layout

- `src/iran_tax_mcp/http.py`: the only HTTP code. One shared `httpx.AsyncClient` (`trust_env=False`, keeps cookies)
  on a Chrome-impersonating curl_cffi transport, optional proxy from `IRAN_TAX_MCP_PROXY` (comma list, sticky, next on
  403/429/connect error), semaphore (4), jitter, retries (2) on timeout/network/5xx/429 for every call (all are reads),
  no redirects, host allowlist, 30 MB body cap, 60 s read timeout, `request()`, `get_form()`/`form_state()` for
  ASP.NET WebForms, `cached(key, ttl, make)`, `ApiError(ToolError)`, `set_transport()` for tests.
- `registry.py`: `@tool("Title")` collects tools (+ `clip`). `server.py`: registers them read-only, holds `INSTRUCTIONS`.
- `goods.py`: `tx_goods_search` (stuffid GraphQL export + guest zip download, CSV ranking), `jalali()`.
- `taxgov.py`: `tx_activity_codes`, `tx_property_value` (WebForms postbacks), `tx_faq_search` (JSON handler).
- `regulation.py`: `tx_regulations_search` (`/lwse` HTML cards), `tx_regulation_text` (`/lwvi`, rows from the
  embedded `let chlist = [...]` JSON, rebuilt into reading order by `pcode`/`ord`).
- `tests/`: offline tests per module (MockTransport + trimmed real pages in `tests/fixtures/`), `test_live_tax.py`
  (`@pytest.mark.live`).

## Commands

```bash
uv sync
uv run ruff check . && uv run ruff format --check .
uv run python -m pytest -q            # offline (`uv run pytest` hits a uv trampoline error on this machine)
uv run python -m pytest -m live -q    # real sites, needs an Iranian connection
uv build
```

## Rules for changes

- Read-only. No captcha solving, no login, no taxpayer keys.
- New tool: `@tool("Title")` async function, every param `Annotated[..., Field(...)]` with an example, first docstring
  line a complete sentence, unit test, live test, README table row, `INSTRUCTIONS` mention.
- Deps stay `mcp` + `httpx` + `httpx-curl-cffi`/`curl-cffi`. Keep `README.md` tools equal to `list_tools()`.
- Persian invisible characters (ZWNJ, soft hyphen, NBSP, BOM) only as `\uXXXX` escapes in code.

## Quirks (keep them, verified 2026-10-20 on a direct Iranian connection)

- Reachability: these hosts timed out through a Turkish proxy exit and answered directly from Iran (MCI). The shell's
  `HTTPS_PROXY` makes plain curl use the proxy; the server ignores env proxies.
- stuffid: `GetInformationWithIDFilter` (title = substring phrase, or `code`) only returns a `fileName` (~13-15 s);
  the zip is at `/portal-gateway/upload/gs/api/v1/exportguest/download/<fileName>` (found in the SPA bundle:
  `exportGuestPath`). CSV columns: ID, DescriptionOfID, Vat, Taxable, RunDate, ExpirationDate, CreateDate,
  LastEditDate, Type, PricingDescription. The site's «من ربات نیستم» box is a plain toggle, not a captcha. `/upload/rest/...`
  (non-guest) is 401. Broad phrases return tens of thousands of rows (لپ تاپ: 23,864); `LIMIT_MAX` 20 keeps replies small.
- tax.gov.ir SearchIntaCode: `ddlIntaCodeTejari` is تجاری (1) / غیرتجاری (0) and has no "all"; empty returns nothing.
  The two numeric columns are profit ratios (نسبت سود فعالیت, نسبت سود ناویژه به فروش), not tax rates.
- tax.gov.ir property value: GET `/GetAddressGeoLocation/30/<lat>/<lng>` only pre-fills the form; the result needs
  the POST with `ButtonSearchGeolocation`. Another year is a second POST with `__EVENTTARGET=DDLLocationYears`.
- tax.gov.ir captcha forms (InquiryNationalID, GetInvalidCompany, 186/187 certificates, stamps) are not used.
- regulation.tax.gov.ir: a search needs `s281010109[]` field selectors (title `s281010107`, text `s281010108`);
  without them the query is ignored and every document of the type comes back (7357 for `all`). 20 results per page,
  offset `fr`. Document text is in `let chlist = [...]` (heading `ti`, HTML `s80512493`, id `tk`, parent `pcode`,
  order `ord`); the array is not in reading order. The direct tax law page is ~1.6 MB; documents are cached 1 h.
- codal.ir (not in this server): its search API rate-limited us after ~50 requests at 1/s (429 + a DDoS captcha).

## Release

Bump `version` in `pyproject.toml` and both versions in `server.json`, commit, then `git tag vX.Y.Z && git push --tags`.
`.github/workflows/publish.yml` tests, publishes to PyPI (trusted publishing), creates the GitHub Release and publishes
to the MCP Registry. Needs the `sepehr071/iran-tax-mcp` GitHub repo and a `uv.lock` committed (`uv sync` makes it).
