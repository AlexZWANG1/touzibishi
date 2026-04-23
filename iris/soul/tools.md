# Tool Routing Guide

Use structured APIs first. Only fall back to web search/fetch when structured sources lack the data.

## Priority Order by Data Need

**Stock price / valuation multiples / market data:**
→ `quote` (one call, has P/E, EV/EBITDA, market cap, 52w range)

**Historical prices / trend:**
→ `history`

**Financial statements (IS / BS / CF / ratios):**
→ `financials` with statement_type = income-statement / balance-sheet-statement / cash-flow-statement / ratios

**Segment / business-unit revenue breakdown:**
→ `financials` with statement_type = `segments` (returns product-line + geographic splits from FMP)
→ If FMP lacks coverage: `sec_filing` action=`section` section_name=`MD&A` (segment discussion in 10-K text)

**Company profile / overview:**
→ `financials` with statement_type = `profile`

**Macroeconomic data (GDP, CPI, rates):**
→ `macro`

**10-K / 10-Q official text (MD&A, Risk Factors, Business description):**
→ `sec_filing` action=`section`

**XBRL financial metrics from latest SEC filing:**
→ `sec_filing` action=`metrics`

**Multi-year time series of a single metric (revenue, net income, EPS, etc.):**
→ `sec_filing` action=`xbrl_timeseries` concept=`RevenueFromContractWithCustomerExcludingAssessedTax`
  (direct SEC API, fast, up to 10 years annual + 8 quarters, no library needed)

**Earnings call transcript / management commentary:**
→ `transcript` (auto-chains: Finnhub → FMP → Exa+Jina web scrape)

**Tech sentiment, community reactions, research trends, industry news:**
→ `news_feed` FIRST — high-quality curated sources (HN, Reddit, arXiv, RSS feeds, YouTube, GitHub Trending). Use this proactively during any analysis to gather real-time market/tech sentiment. It returns titles, URLs, scores, and summaries.
→ Then `exa_search` for targeted follow-up queries not covered by news_feed
→ Then `web_fetch` only if you need full article text from a specific URL found above

**Arbitrary web page content:**
→ `web_fetch` (last resort — high failure rate on paywalled sites)

## Rules

1. **Never use `web_fetch` to get data available from structured tools.** Financial statements, segment data, stock quotes, SEC filings — all have dedicated tools.
2. **`news_feed` before `exa_search` for sentiment/trends.** news_feed pulls from 62+ curated, high-quality sources maintained by the user. Use it proactively when analyzing any company or sector — don't wait for the user to ask for news. Typical pattern: `news_feed(sources=["hackernews","reddit","arxiv"], topic="company or sector keyword")`.
3. **`exa_search` finds, `web_fetch` reads.** exa_search returns URLs and snippets. Only call web_fetch if the snippet is insufficient and you need full text.
4. **Do not retry failed `web_fetch` on similar URLs.** If Yahoo Finance / Fortune / Investopedia return 451, they block automated access. Move on.
5. **One `sec_filing` call replaces 10+ web_fetch attempts.** For segment data, MD&A text, or risk factors — use sec_filing, not web scraping.
6. **Budget awareness:** You have ~60 tool calls per analysis. Plan ahead. A typical deep analysis should use ≤30 tool calls.
