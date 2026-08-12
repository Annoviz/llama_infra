# Open-WebSearch vs Firecrawl — Detailed Comparison

> Research date: August 2026
> Sources: GitHub repos, official docs, pricing pages

## Overview

| | **open-webSearch** | **Firecrawl** |
|---|---|---|
| **Repo** | [Aas-ee/open-webSearch](https://github.com/Aas-ee/open-webSearch) | [firecrawl/firecrawl](https://github.com/firecrawl/firecrawl) |
| **Stars** | ~1.7k | ~166k |
| **License** | Apache-2.0 | AGPL-3.0 (core), MIT (SDKs/UI) |
| **Language** | TypeScript | TypeScript/Node.js monorepo |
| **Primary focus** | Web search aggregation for AI agents | Full web data infrastructure (search, scrape, crawl, interact) |
| **Hosted service** | No — self-host only | Yes — firecrawl.dev + self-host option |
| **API keys required** | None | Required for cloud; optional for self-host |

---

## Feature Comparison

### Core Capabilities

| Feature | open-webSearch | Firecrawl |
|---|---|---|
| **Web search** | Multi-engine aggregation (Bing, DuckDuckGo, Brave, Exa, Baidu, Sogou, Startpage, CSDN, Juejin) | Built-in search index + live web scraping |
| **URL scraping** | Limited — fetch specific site content (CSDN, GitHub README, Juejin, generic web/Markdown) | Full-page scrape to Markdown, HTML, JSON, screenshots |
| **Site crawling** | No | Yes — recursive crawl with depth/path limits |
| **Site mapping** | No | Yes — discover all URLs on a site instantly |
| **Batch operations** | No | Yes — batch scrape thousands of URLs async |
| **Browser interaction** | Optional Playwright fallback for search only | Full interact API — click, scroll, type, wait, press |
| **AI agent endpoint** | No | Yes — describe what you need, agent finds it |
| **Structured data extraction** | No | Yes — JSON schema-based extraction |
| **Media parsing** | No | Yes — PDFs, DOCX, and more |
| **Web monitoring** | No | Yes — scheduled page checks |

### MCP & Agent Integration

| Feature | open-webSearch | Firecrawl |
|---|---|---|
| **MCP server** | Yes — primary delivery mode (stdio + HTTP/SSE) | Yes — official `firecrawl-mcp` package |
| **CLI** | Yes — built-in CLI and local daemon | Yes — `firecrawl-cli` with skills system |
| **Agent skill** | Yes — `npx skills add` workflow | Yes — agent onboarding + skill files |
| **Claude/Cursor/Cherry Studio** | First-class support | First-class support |
| **Zapier/n8n** | No | Yes |

### Deployment & Infrastructure

| Feature | open-webSearch | Firecrawl |
|---|---|---|
| **Docker image** | Yes — `ghcr.io/aas-ee/open-web-search` | Yes — full Compose stack |
| **Docker Compose** | Yes — single service | Yes — multi-service (API, Redis, PostgreSQL, RabbitMQ, Playwright) |
| **NPX one-liner** | Yes — `npx open-websearch@latest` | Yes — `npx -y firecrawl-cli@latest` |
| **Self-host complexity** | Low — single container, no dependencies | High — full microservice stack |
| **Resource requirements** | Minimal (Node.js process) | Significant (multiple services, browser instances) |
| **SDKs** | None (MCP/CLI only) | Python, Node.js, Go, Rust, Java, Elixir, Ruby, .NET, PHP |

### Pricing & Cost

| Aspect | open-webSearch | Firecrawl |
|---|---|---|
| **Self-host cost** | Free (your infra) | Free (AGPL-3.0, your infra) |
| **Cloud free tier** | N/A | 1,000 credits/month |
| **Hobby plan** | N/A | $16/mo — 5k credits |
| **Standard plan** | N/A | $83/mo — 100k credits |
| **Growth plan** | N/A | $333/mo — 500k credits |
| **Scale plan** | N/A | $599/mo — 1M credits |
| **Enterprise** | N/A | Custom pricing |
| **Credit cost** | N/A | Scrape: 1/page, Search: 2/10 results, Interact: 2/min |

---

## Pros and Cons

### open-webSearch

**Pros:**
- Zero API keys — works out of the box with free search engines
- Lightweight — single Node.js process, minimal resource footprint
- Multi-engine aggregation — combine results from Bing, DuckDuckGo, Brave, Exa, Baidu, Sogou, Startpage, CSDN, Juejin
- Simple deployment — `npx` one-liner or single Docker container
- Apache-2.0 license — permissive for commercial use
- No rate limits from a central provider (limited only by search engines' own policies)
- Good for regions where Google is restricted (Baidu, Sogou, CSDN support)
- Playwright fallback for anti-bot protection on Bing

**Cons:**
- Search-only — no crawling, scraping, or structured extraction
- Limited content fetching — only specific sites (CSDN, GitHub, Juejin, generic Markdown)
- No browser interaction capabilities
- Small community (~1.7k stars) — fewer contributors and integrations
- Reliability depends on search engine HTML structure — fragile to site changes
- No hosted/cloud option — you manage everything
- No SDKs — MCP/CLI only
- Rate limiting from upstream engines can block high-volume usage

### Firecrawl

**Pros:**
- Comprehensive web data platform — search, scrape, crawl, map, interact, monitor
- 166k GitHub stars — massive community and ecosystem
- Hosted cloud service with free tier — no infrastructure management needed
- Rich SDKs in 9 languages — Python, Node.js, Go, Rust, Java, Elixir, Ruby, .NET, PHP
- Structured data extraction via JSON schemas
- Browser interaction API for complex pages (click, scroll, type)
- AI agent endpoint — natural language data gathering
- Media parsing (PDFs, DOCX)
- Enterprise features: SOC 2 compliance, SSO, zero-data retention
- Integrations with Zapier, n8n, Lovable, and more
- 96% web coverage including JS-heavy pages
- P95 latency of 3.4s across millions of pages

**Cons:**
- AGPL-3.0 license — copyleft requirements for self-hosted modifications
- Complex self-host stack — requires PostgreSQL, Redis, RabbitMQ, Playwright services
- Cloud pricing can add up at scale ($599/mo for 1M credits)
- Credits don't roll over on self-serve plans
- Self-hosted version lacks key features (screenshots, interact, Fire-engine anti-bot)
- Requires API key for cloud usage
- Heavy resource requirements for self-hosted deployment

---

## When to Use Each

### Choose open-webSearch when:
- You need a **simple, free web search tool** for AI agents
- You want **zero configuration** — no API keys, no accounts
- You're in a region where **Google is restricted** and need Baidu/Sogou/CSDN access
- You have **limited infrastructure** and can't run a full microservice stack
- You only need search results (titles, URLs, descriptions), not full page content
- You want a **permissive Apache-2.0 license** for commercial embedding

### Choose Firecrawl when:
- You need **full web data extraction** — scraping, crawling, structured data
- You want a **managed cloud service** with reliability guarantees
- You need **browser interaction** for complex pages behind logins or pagination
- You're building **enterprise-grade** pipelines with SOC 2 compliance
- You need **multi-language SDKs** for diverse tech stacks
- You want **batch operations** — crawling entire sites or scraping thousands of URLs
- You need **AI-powered data gathering** via the Agent endpoint

---

## Architecture Summary

### open-webSearch
```
Agent/MCP Client → open-webSearch (single Node.js process)
                         ↓
              ┌──────────┼──────────┐
              ↓          ↓          ↓
           Bing      DuckDuckGo   Brave/Exa/etc.
           (HTTP)     (HTTP)      (HTTP)
              ↓
         Structured results (title, URL, description)
```

### Firecrawl
```
Agent/SDK → Firecrawl API
                ↓
    ┌───────────┼────────────┐
    ↓           ↓            ↓
 Scrape      Crawl          Search
 Engine      Queue          Index
    ↓           ↓            ↓
 Playwright  PostgreSQL   Web + Cache
 Browser     Redis        Live fetch
    ↓
 Clean Markdown / JSON / Screenshots
```

---

## Verdict for llama_infra Context

For our local AI agent infrastructure, **open-webSearch** is the right choice for:
- Lightweight MCP-based web search without external dependencies
- Cost-free operation with no API key management
- Simple Docker deployment alongside existing services

**Firecrawl** would be better if we needed:
- Full-page content extraction from arbitrary URLs
- Site-wide crawling for documentation ingestion
- Structured data extraction with schemas
- Browser interaction for authenticated pages

The existing `open-webSearch` MCP server in our stack covers the search use case well. Firecrawl's cloud service could complement it for heavy scraping needs, but the self-hosted complexity and AGPL license make it less attractive for our setup.
