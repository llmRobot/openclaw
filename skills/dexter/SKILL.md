---
name: dexter
description: Autonomous financial research agent for stock analysis, financial statements, metrics, prices, SEC filings, and crypto data.
metadata: {"clawdbot":{"emoji":"📊","os":["darwin","linux"],"requires":{"bins":["bun","git"]}}}
---

# Dexter Skill (Clawdbot)

Dexter is an autonomous financial research agent that plans, executes, and synthesizes financial data analysis. Use it for any financial research question involving stocks, crypto, company fundamentals, or market data.

## When to Use Dexter

Use Dexter for:
- Stock prices (current and historical)
- Financial statements (income, balance sheet, cash flow)
- Financial metrics (P/E, P/B, margins, market cap, etc.)
- SEC filings (10-K, 10-Q, 8-K)
- Analyst estimates
- Insider trades
- Company news
- Crypto prices
- Comparative financial analysis
- Revenue trends and growth rates

**Note**: Dexter's Financial Datasets API covers primarily US stocks. For international stocks (like European exchanges), it falls back to web search via Tavily.

## Installation

### 1. Clone and Install

```bash
DEXTER_DIR="/root/clawd-workspace/dexter"

if [ ! -d "$DEXTER_DIR" ]; then
  git clone https://github.com/virattt/dexter.git "$DEXTER_DIR"
fi

cd "$DEXTER_DIR"
bun install
```

### 2. Configure API Keys

Create `.env` file with required API keys:

```bash
cat > "$DEXTER_DIR/.env" << 'EOF'
ANTHROPIC_API_KEY=your-anthropic-key
FINANCIAL_DATASETS_API_KEY=your-financial-datasets-key
TAVILY_API_KEY=your-tavily-key
EOF
```

**API Key Sources:**
- Anthropic: https://console.anthropic.com/
- Financial Datasets: https://financialdatasets.ai (free tier available)
- Tavily: https://tavily.com (optional, for web search fallback)

### 3. Configure Model Settings

```bash
mkdir -p "$DEXTER_DIR/.dexter"
cat > "$DEXTER_DIR/.dexter/settings.json" << 'EOF'
{
  "provider": "anthropic",
  "modelId": "claude-sonnet-4-5"
}
EOF
```

## Usage

```bash
cd $DEXTER_DIR
bun run src/cli.ts "What is Apple's revenue growth?"
```
