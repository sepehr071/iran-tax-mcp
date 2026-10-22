<!-- mcp-name: io.github.sepehr071/iran-tax-mcp -->

# iran-tax-mcp: Iranian tax MCP server for AI agents

**Let your AI agent answer Iranian tax questions (مالیات) from the tax administration's own public systems.**<br>
An unofficial, read-only MCP server over [tax.gov.ir](https://tax.gov.ir), the goods/service ID system [stuffid.tax.gov.ir](https://stuffid.tax.gov.ir) and the tax regulation database [regulation.tax.gov.ir](https://regulation.tax.gov.ir):<br>
e-invoice goods IDs and VAT rates, activity codes, property transaction values, tax laws, circulars and rulings, and the official FAQ.

[![PyPI](https://img.shields.io/pypi/v/iran-tax-mcp?color=2563eb)](https://pypi.org/project/iran-tax-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/iran-tax-mcp)](https://pypi.org/project/iran-tax-mcp/)
[![CI](https://github.com/sepehr071/iran-tax-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/sepehr071/iran-tax-mcp/actions/workflows/ci.yml)
[![MCP Registry](https://img.shields.io/badge/MCP_Registry-io.github.sepehr071%2Firan--tax--mcp-7c3aed)](https://registry.modelcontextprotocol.io/?q=iran-tax-mcp)
[![License: MIT](https://img.shields.io/badge/license-MIT-16a34a)](https://github.com/sepehr071/iran-tax-mcp/blob/main/LICENSE)

[![Install in VS Code](https://img.shields.io/badge/VS_Code-Install_iran--tax--mcp-0098FF?style=flat-square&logo=visualstudiocode&logoColor=white)](https://vscode.dev/redirect/mcp/install?name=iran-tax&config=%7B%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22iran-tax-mcp%22%5D%7D)

[For AI agents](#for-ai-agents) · [Why](#why) · [What it can do](#what-it-can-do) · [Quick start](#quick-start) · [Tools](#tools) · [How it works](#how-it-works) · [Good to know](#good-to-know) · [FAQ](#faq) · [Configuration](#configuration) · [فارسی](#فارسی) · [Development](#development)

---

## For AI agents

- **What:** unofficial MCP server (model context protocol) for public services of the Iranian National Tax Administration (سازمان امور مالیاتی کشور): tax.gov.ir, stuffid.tax.gov.ir and regulation.tax.gov.ir. Answers are Persian text.
- **Install:** `uvx iran-tax-mcp` or `claude mcp add iran-tax -- uvx iran-tax-mcp`. Transport: stdio. Needs [uv](https://docs.astral.sh/uv/getting-started/installation/) (Python 3.10+).
- **Auth:** none, no API key or account. Optional `IRAN_TAX_MCP_PROXY` (HTTP proxy URL, or a comma-separated list); system proxy settings are ignored. The sites often refuse foreign IPs: outside Iran, use a proxy that exits in Iran.
- **Access:** read-only. No login, filing, invoicing or payment, so no confirmation is needed before calling any tool.
- **Tools:** 6, all prefixed `tx_`: `tx_goods_search`, `tx_activity_codes`, `tx_property_value`, `tx_regulations_search`, `tx_regulation_text`, `tx_faq_search`. For a law question, call `tx_regulations_search` first, then pass the hit's `id` and `type` to `tx_regulation_text`.
- **Use when:** a company or accountant needs an e-invoice goods/service ID and its VAT rate, an activity code and its VAT stage, the official property value at an address, the text of a tax law article, a circular (بخشنامه) or ruling, or an official FAQ answer.
- **Do not use when:** the task needs a taxpayer's own data (returns, invoices, debts, economic-code lookups). Those need a login or a captcha and are not offered.
- **Output:** compact JSON. Dates and years are Jalali (`1405/07/27`, `1404`). Money is rial as integers. Null and empty fields are omitted. Replies stay under ~15 KB: long texts come in parts of 6000 characters, list sizes are capped.
- **Network:** the first `tx_goods_search` for a phrase takes 15-30 s (cached for an hour).
- **Machine-readable:** [`server.json`](https://github.com/sepehr071/iran-tax-mcp/blob/main/server.json) and the
  [awesome-iran-mcp catalog](https://github.com/sepehr071/awesome-iran-mcp).

## Why

Iranian tax answers live on three different government sites, each with its own forms, postbacks and search screens. Finding the VAT rate of a product means a slow ID search; finding article 169 bis of the direct tax law means scrolling a 1.6 MB page. With `iran-tax-mcp` an agent runs the search, picks the right document and returns just the part you asked for.

> **You:** What is the VAT treatment of laptops on the e-invoice system?
>
> **Agent:** *calls* `tx_goods_search(query="لپ تاپ", limit=5)`
>
> It returns the best-ranked active general goods IDs with their VAT rate, type and validity dates.

Every reply is trimmed to stay under about 15 KB, so it does not flood the agent's context.

## What it can do

- **Find e-invoice goods and service IDs** (شناسه کالا و خدمات) by description or 13-digit ID, with VAT rate, type and validity
- **Look up activity codes** (اینتاکد) with VAT stage, business group and the official profit ratios
- **Get the official property value** (ارزش معاملاتی) and rent value per m², booklet block and row, and the tax offices for a map point
- **Search tax laws, regulations, circulars, rulings, opinions, correspondence and glossary**, newest first
- **Read the full text** of one document, or a single article such as `ماده 169 مکرر`, with the official PDF link
- **Search the official FAQ** of the tax administration
- **Read-only by design**: no login, no filing, no payment

Example prompts:

- "Find the e-invoice goods ID and VAT rate for a laptop."
- "Which activity code fits a restaurant, and what are its profit ratios for 1404?"
- "What is the official property value per m² at latitude 35.70, longitude 51.40?"
- "Show article 169 bis (مکرر) of the direct tax law."
- "Latest circulars about VAT on e-invoicing."
- <span dir="rtl">شناسه کالا و خدمات برای لپ&zwnj;تاپ چیست و نرخ ارزش افزوده آن چقدر است؟</span>
- <span dir="rtl">متن ماده ۱۶۹ مکرر قانون مالیات&zwnj;های مستقیم را بیاور.</span>
- <span dir="rtl">ارزش معاملاتی ملک در این مختصات چقدر است؟</span>

## Quick start

You need [uv](https://docs.astral.sh/uv/getting-started/installation/). No API key or account. Outside Iran, see the proxy note in [Good to know](#good-to-know).

<details open>
<summary><b>Claude Code</b></summary>

```bash
claude mcp add iran-tax -- uvx iran-tax-mcp
```
</details>

<details>
<summary><b>Claude Desktop</b></summary>

Settings → Developer → Edit Config, then add:

```json
{
  "mcpServers": {
    "iran-tax": { "command": "uvx", "args": ["iran-tax-mcp"] }
  }
}
```
</details>

<details>
<summary><b>Cursor</b></summary>

Add the Claude Desktop block above to `~/.cursor/mcp.json` (or `.cursor/mcp.json` in a project).
</details>

<details>
<summary><b>VS Code (Copilot agent mode)</b></summary>

Click **Install in VS Code** above, or add to `.vscode/mcp.json`:

```json
{
  "servers": {
    "iran-tax": { "type": "stdio", "command": "uvx", "args": ["iran-tax-mcp"] }
  }
}
```
</details>

<details>
<summary><b>Codex CLI</b></summary>

```bash
codex mcp add iran-tax -- uvx iran-tax-mcp
```

Or in `~/.codex/config.toml`:

```toml
[mcp_servers.iran-tax]
command = "uvx"
args = ["iran-tax-mcp"]
```
</details>

<details>
<summary><b>Gemini CLI</b></summary>

Add to `~/.gemini/settings.json`:

```json
{
  "mcpServers": {
    "iran-tax": { "command": "uvx", "args": ["iran-tax-mcp"] }
  }
}
```
</details>

<details>
<summary><b>Windsurf</b></summary>

Add the Claude Desktop block to `~/.codeium/windsurf/mcp_config.json`.
</details>

<details>
<summary><b>Anything else</b></summary>

It is a standard stdio MCP server: run `uvx iran-tax-mcp`, or `pip install iran-tax-mcp` and run `iran-tax-mcp`.
</details>

## Tools

| Tool | What it does |
|---|---|
| `tx_goods_search` | E-invoice goods/service IDs (شناسه کالا و خدمات) with VAT rate, type and validity, by description or 13-digit ID (`query`, `kind`, `general_only`, `limit` 1-20). First search for a phrase takes 15-30 s; cached for an hour. |
| `tx_activity_codes` | Activity codes (اینتاکد) with VAT stage, business group and official profit ratios (`query`, `year`, `commercial`, `limit` 1-20). |
| `tx_property_value` | Official property transaction value (ارزش معاملاتی) and rent value per m², booklet block and row, and the tax offices for a point (`latitude`, `longitude`, `year`). |
| `tx_regulations_search` | Search tax laws, regulations and circulars, rulings, opinions, correspondence and glossary, newest first (`query`, `type`, `title_only`, `page`). |
| `tx_regulation_text` | Full text of one document, or one article of it such as `ماده 169 مکرر`, with metadata and the official PDF link (`id`, `type`, `article`, `part`). |
| `tx_faq_search` | The tax administration's FAQ: matching questions with links (`query`). |

All 6 tools are annotated `readOnlyHint: true`.

## How it works

```text
  AI agent  (Claude, Cursor, Copilot, ...)
      │
      │  MCP over stdio
      ▼
  iran-tax-mcp  (runs on your machine)
      │
      │  HTTPS
      ├──────▶  tax.gov.ir              activity codes, property values, FAQ
      ├──────▶  stuffid.tax.gov.ir      goods/service IDs and VAT
      └──────▶  regulation.tax.gov.ir   laws, circulars, rulings
```

`iran-tax-mcp` runs locally and reads the same public pages and endpoints the three sites use. It has no hosted server in between and no API key. Requests go out through a Chrome-impersonating client, at most 4 at a time with a little jitter, retried up to twice on timeouts, network errors, 5xx and 429. It only talks to the allowed tax hosts and only reads.

## Good to know

- **Network:** these sites timed out through a Turkish proxy exit and answered directly from an Iranian connection. Outside Iran, set `IRAN_TAX_MCP_PROXY` to an HTTP proxy with an Iranian exit. System proxy variables are ignored on purpose.
- **Slow first goods search:** the ID system builds a file for each search (15-30 s for a broad phrase such as «لپ تاپ», which has tens of thousands of rows). The server downloads and ranks it (active general IDs first) and keeps it for an hour. Replies are capped at 20 rows.
- **Activity codes:** the two numeric columns are profit ratios (نسبت سود فعالیت, نسبت سود ناویژه به فروش), not tax rates. The commercial/non-commercial switch (تجاری / غیرتجاری) has no "all" option.
- **Property values:** the result is the official transaction value for a point, for a chosen year.
- **Regulation text:** long documents come in parts of 6000 characters; ask for the next `part`, or for a single article. Documents are cached for an hour.
- **Units:** years and dates are Jalali, money is rial as integers.
- **What it does not do:** no economic-code (شماره اقتصادی) or invalid-company lookup, no certificates, no returns, invoices or payments, no login and no captcha solving.

## FAQ

<details>
<summary><b>Is there an API or MCP server for Iranian tax data?</b></summary>

The tax administration's public sites have no documented open API for these lookups. `iran-tax-mcp` is an unofficial MCP server with 6 read-only tools that reads the public pages of tax.gov.ir, stuffid.tax.gov.ir and regulation.tax.gov.ir and returns compact JSON for AI agents.
</details>

<details>
<summary><b>Does it work outside Iran?</b></summary>

Often not: Iranian government sites drop many foreign connections. It was built and tested on a direct Iranian connection. Set `IRAN_TAX_MCP_PROXY` to a proxy in Iran if calls fail to connect.
</details>

<details>
<summary><b>Why no economic-code (شماره اقتصادی) or invalid-company lookup?</b></summary>

On tax.gov.ir those forms need a captcha, and the e-invoice API needs the taxpayer's signed key. This server only uses what is public without either.
</details>

<details>
<summary><b>Why is the first goods search slow?</b></summary>

The ID system answers a search by building a file (15-30 s for a broad phrase such as «لپ تاپ»). The server downloads it once, ranks it (active general IDs first) and keeps it for an hour, so repeats are fast.
</details>

<details>
<summary><b>How do I get the text of a specific law article?</b></summary>

Call `tx_regulations_search` to find the document, then `tx_regulation_text` with its `id` and `type`, and `article` set to something like `ماده 169 مکرر`.
</details>

<details>
<summary><b>Are the activity-code numbers tax rates?</b></summary>

No. The two numeric columns are the official profit ratios (نسبت سود فعالیت and نسبت سود ناویژه به فروش).
</details>

<details>
<summary><b>Can it file returns, issue invoices or pay taxes?</b></summary>

No. It has no login and no write calls, it only reads public information. Nothing it returns is tax or legal advice.
</details>

<details>
<summary><b>How do I debug what the agent sees?</b></summary>

```bash
npx @modelcontextprotocol/inspector uvx iran-tax-mcp
```
</details>

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `IRAN_TAX_MCP_PROXY` | unset | Optional HTTP proxy URL for requests to the tax sites; system proxy settings are ignored. A comma-separated list is used one at a time: the next proxy takes over when one is blocked or cannot connect |

<a id="فارسی"></a>

## فارسی: سرور MCP مالیات ایران

<div dir="rtl">

**iran-tax-mcp** یک سرور MCP غیررسمی و فقط&zwnj;خواندنی برای خدمات عمومی سازمان امور مالیاتی کشور است. این سرور به دستیار هوش مصنوعی شما (Claude، Cursor، Copilot و ...) اجازه می&zwnj;دهد در سامانه&zwnj;های tax.gov.ir، stuffid.tax.gov.ir و regulation.tax.gov.ir جست&zwnj;وجو کند.

**چه کارهایی می&zwnj;کند**

- **شناسه کالا و خدمات** (صورتحساب الکترونیکی، سامانه مودیان) و نرخ ارزش افزوده، با توضیح کالا یا شناسه ۱۳ رقمی.
- **کد فعالیت (اینتاکد)** با مرحله ارزش افزوده و نسبت سود رسمی.
- **ارزش معاملاتی املاک** و ارزش اجاره هر متر مربع بر اساس مختصات.
- **قوانین، بخشنامه&zwnj;ها، دستورالعمل&zwnj;ها و آرای مالیاتی** از سامانه جامع مقررات مالیاتی، با متن کامل یا یک ماده مشخص مثل «ماده ۱۶۹ مکرر».
- **پرسش&zwnj;های متداول** سازمان امور مالیاتی.

**نکته&zwnj;ها**

- فقط خواندنی است: وارد حساب نمی&zwnj;شود، اظهارنامه نمی&zwnj;دهد و پرداخت انجام نمی&zwnj;دهد. مشاوره مالیاتی یا حقوقی نیست.
- استعلام شماره اقتصادی و شرکت&zwnj;های نامعتبر ارائه نمی&zwnj;شود (کپچا یا ورود لازم دارد).
- سال و تاریخ شمسی است و مبالغ به ریال.
- جست&zwnj;وجوی اول شناسه کالا ۱۵ تا ۳۰ ثانیه طول می&zwnj;کشد و بعد یک ساعت ذخیره می&zwnj;شود.
- این سامانه&zwnj;ها اغلب IP خارجی را قبول نمی&zwnj;کنند؛ از اینترنت ایران استفاده کنید یا متغیر `IRAN_TAX_MCP_PROXY` را روی یک پراکسی HTTP با خروجی ایران بگذارید.
- کلید API لازم نیست و روی سیستم خود شما اجرا می&zwnj;شود.

**نصب** (اول [uv](https://docs.astral.sh/uv/getting-started/installation/) را نصب کنید). در Claude Code:

</div>

```bash
claude mcp add iran-tax -- uvx iran-tax-mcp
```

<div dir="rtl">

در Claude Desktop، Cursor و بقیه برنامه&zwnj;ها همان تنظیم بخش [Quick start](#quick-start) را بگذارید.

**نمونه پرسش&zwnj;ها**

- «شناسه کالا و خدمات لپ&zwnj;تاپ و نرخ مالیات بر ارزش افزوده آن چیست؟»
- «متن ماده ۱۶۹ مکرر قانون مالیات&zwnj;های مستقیم را بده.»
- «آخرین بخشنامه&zwnj;های مربوط به صورتحساب الکترونیکی کدام&zwnj;اند؟»
- «کد اینتاکد برای رستوران چیست؟»

</div>

## Development

```bash
git clone https://github.com/sepehr071/iran-tax-mcp && cd iran-tax-mcp
uv sync
uv run ruff check . && uv run ruff format --check .
uv run python -m pytest -q          # offline unit tests
uv run python -m pytest -m live -q  # calls the real tax sites, needs an Iranian connection
uv build
```

Tools live in `src/iran_tax_mcp/` (`goods.py`, `taxgov.py`, `regulation.py`); each is a typed async function with a docstring that tells the agent when to use it. Issues and PRs are welcome.

Releases: bump the version in `pyproject.toml` and `server.json`, then push a `v*` tag. GitHub Actions publishes to PyPI.

## Related servers

- [awesome-iran-mcp](https://github.com/sepehr071/awesome-iran-mcp): catalog of all Iranian-service MCP servers
- [qavanin-mcp](https://github.com/sepehr071/qavanin-mcp) for Iranian laws and regulations
- [iran-news-mcp](https://github.com/sepehr071/iran-news-mcp) for Iranian news
- [tgju-mcp](https://github.com/sepehr071/tgju-mcp) for dollar, gold and coin prices
- [tsetmc-mcp](https://github.com/sepehr071/tsetmc-mcp) for the Tehran Stock Exchange

## Disclaimer

Unofficial and not affiliated with or endorsed by the Iranian National Tax Administration (سازمان امور مالیاتی کشور). It is read-only and uses public pages of tax.gov.ir, stuffid.tax.gov.ir and regulation.tax.gov.ir, which can change without notice. Information is for reference only and is not tax or legal advice.

## Author

<a href="https://www.linkedin.com/in/sepehr-radmard"><img src="https://raw.githubusercontent.com/sepehr071/awesome-iran-mcp/main/assets/author-banner.png" alt="Sepehr Radmard: open-source MCP servers for the Iranian web. LinkedIn: linkedin.com/in/sepehr-radmard" width="100%"></a>

Built and maintained by **Sepehr Radmard** (سپهر رادمرد). Connect on [LinkedIn](https://www.linkedin.com/in/sepehr-radmard) or follow [@sepehr071 on GitHub](https://github.com/sepehr071) for more MCP servers for Iranian websites, all listed in [awesome-iran-mcp](https://github.com/sepehr071/awesome-iran-mcp). If this saves you time, a star on the repo helps other people find it.

## License

[MIT](https://github.com/sepehr071/iran-tax-mcp/blob/main/LICENSE)
