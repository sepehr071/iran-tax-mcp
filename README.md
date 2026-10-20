<!-- mcp-name: io.github.sepehr071/iran-tax-mcp -->

# iran-tax-mcp: Iranian tax services MCP server for AI agents

**Let your AI agent answer Iranian tax questions (مالیات) from the tax administration's own public systems.**<br>
An unofficial, read-only MCP server over tax.gov.ir, the goods/service ID system (stuffid.tax.gov.ir) and the tax regulation database (regulation.tax.gov.ir): e-invoice goods IDs and VAT rates, activity codes, property transaction values, tax laws, circulars and rulings, and the official FAQ.

[For AI agents](#for-ai-agents) · [Quick start](#quick-start) · [Tools](#tools) · [FAQ](#faq) · [فارسی](#فارسی)

---

## For AI agents

- **What:** unofficial MCP server for public services of the Iranian National Tax Administration (سازمان امور مالیاتی کشور): tax.gov.ir, stuffid.tax.gov.ir and regulation.tax.gov.ir. Persian text.
- **Install:** `uvx iran-tax-mcp` or `claude mcp add iran-tax -- uvx iran-tax-mcp`. Transport: stdio. Needs [uv](https://docs.astral.sh/uv/getting-started/installation/) (Python 3.10+).
- **Auth:** none. Optional `IRAN_TAX_MCP_PROXY` (HTTP proxy URL, or a comma-separated list); system proxy settings are ignored. The sites often refuse foreign IPs: outside Iran, use a proxy that exits in Iran.
- **Access:** read-only. No login, filing, invoicing or payment, so no confirmation is needed before calling any tool.
- **Tools:** 6: `tx_goods_search`, `tx_activity_codes`, `tx_property_value`, `tx_regulations_search`, `tx_regulation_text`, `tx_faq_search`.
- **Use when:** a company or accountant needs an e-invoice goods/service ID and its VAT rate, an activity code and its VAT stage, the official property value at an address, the text of a tax law article, a circular (بخشنامه) or ruling, or an official FAQ answer.
- **Do not use when:** the task needs a taxpayer's own data (returns, invoices, debts, economic-code lookups). Those need a login or a captcha and are not offered.
- **Output:** compact JSON. Dates and years are Jalali (`1405/07/27`, `1404`). Money is rial as integers. Null and empty fields are omitted. Replies stay under ~15 KB: long texts come in parts of 6000 characters, list sizes are capped.
- **Machine-readable:** [`server.json`](https://github.com/sepehr071/iran-tax-mcp/blob/main/server.json) and the
  [awesome-iran-mcp catalog](https://github.com/sepehr071/awesome-iran-mcp).

## Quick start

```bash
claude mcp add iran-tax -- uvx iran-tax-mcp
```

Other clients: command `uvx`, args `["iran-tax-mcp"]`.

## Tools

| Tool | What it does |
|---|---|
| `tx_goods_search` | E-invoice goods/service IDs (شناسه کالا و خدمات) with VAT rate, type and validity, by description or 13-digit ID (`query`, `kind`, `general_only`, `limit` 1-20). First search for a phrase takes 15-30 s; cached for an hour. |
| `tx_activity_codes` | Activity codes (اینتاکد) with VAT stage, business group and official profit ratios (`query`, `year`, `commercial`, `limit` 1-20). |
| `tx_property_value` | Official property transaction value (ارزش معاملاتی) and rent value per m², booklet block and row, and the tax offices for a point (`latitude`, `longitude`, `year`). |
| `tx_regulations_search` | Search tax laws, regulations and circulars, rulings, opinions, correspondence and glossary, newest first (`query`, `type`, `title_only`, `page`). |
| `tx_regulation_text` | Full text of one document, or one article of it such as `ماده 169 مکرر`, with metadata and the official PDF link (`id`, `type`, `article`, `part`). |
| `tx_faq_search` | The tax administration's FAQ: matching questions with links (`query`). |

## FAQ

**Does it work outside Iran?** Often not: Iranian government sites drop many foreign connections. It was built and tested on a direct Iranian connection. Set `IRAN_TAX_MCP_PROXY` to a proxy in Iran if calls fail to connect.

**Why no economic-code (شماره اقتصادی) or invalid-company lookup?** On tax.gov.ir those forms need a captcha, and the e-invoice API needs the taxpayer's signed key. This server only uses what is public without either.

**Why is the first goods search slow?** The ID system answers a search by building a file (15-30 s for a broad phrase such as «لپ تاپ», tens of thousands of rows). The server downloads it once, ranks it (active general IDs first) and keeps it for an hour.

## فارسی

سرور MCP غیررسمی و فقط‌خواندنی برای خدمات عمومی سازمان امور مالیاتی کشور: جست‌وجوی شناسه کالا و خدمات (صورتحساب الکترونیکی) و نرخ ارزش افزوده، کد فعالیت (اینتاکد)، ارزش معاملاتی املاک، متن قوانین، بخشنامه‌ها و آرای مالیاتی از سامانه جامع مقررات مالیاتی، و پرسش‌های متداول.

```bash
claude mcp add iran-tax -- uvx iran-tax-mcp
```
