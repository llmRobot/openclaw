---
name: annual-report
description: 上市公司年报获取与深度分析技能。支持自动下载年报PDF、三表解析、财务指标计算、文本分析、异常检测。
---

# 上市公司年报分析技能

## 概述

获取上市公司年报并进行深度分析，支持：
- **年报获取**：从上交所、巨潮资讯、东方财富等渠道下载年报 PDF
- **三表解析**：利润表、资产负债表、现金流量表结构化提取
- **财务指标**：盈利、偿债、成长等核心指标计算
- **文本分析**：MD&A 提取、审计意见识别、风险披露分析
- **异常检测**：多年趋势对比、财务造假预警

## 依赖安装

```bash
pip install pdfplumber requests beautifulsoup4 pandas
```

## 使用方法

### 1. 下载年报

```bash
python3 /skills/annual-report/scripts/annual_report.py --action download --symbol 600519 --year 2023
```

### 2. 手动导入本地 PDF

如果自动下载失败，可以手动下载后导入：

```bash
# 1. 从以下渠道手动下载年报 PDF：
#    - 巨潮资讯: http://www.cninfo.com.cn
#    - 上交所: http://www.sse.com.cn
#    - 深交所: http://www.szse.cn
#    - 东方财富: https://data.eastmoney.com

# 2. 导入本地文件
python3 /skills/annual-report/scripts/annual_report.py \
  --action import \
  --local-path /path/to/report.pdf \
  --symbol 600519 \
  --year 2023
```

### 3. 列出已有年报

```bash
python3 /skills/annual-report/scripts/annual_report.py --action list
python3 /skills/annual-report/scripts/annual_report.py --action list --symbol 600519
```

### 4. 解析年报

```bash
python3 /skills/annual-report/scripts/annual_report.py --action parse --symbol 600519 --year 2023
```

### 5. 财务指标分析

```bash
python3 /skills/annual-report/scripts/annual_report.py --action analyze --symbol 600519 --year 2023
```

### 6. 文本分析

```bash
python3 /skills/annual-report/scripts/annual_report.py --action text_analysis --symbol 600519 --year 2023
```

### 7. 完整分析报告

```bash
python3 /skills/annual-report/scripts/annual_report.py --action full_report --symbol 600519 --year 2023
```

### 8. 多年对比

```bash
python3 /skills/annual-report/scripts/annual_report.py --action compare --symbol 600519 --years 2021,2022,2023
```

### 9. 异常检测

```bash
python3 /skills/annual-report/scripts/annual_report.py --action detect_anomaly --symbol 600519 --years 2021,2022,2023
```

## 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--action` | 操作类型: download, import, list, parse, analyze, text_analysis, full_report, compare, detect_anomaly | 必填 |
| `--symbol` | 股票代码 | 大部分操作必填 |
| `--year` | 年报年份 | 大部分操作必填 |
| `--years` | 多个年份（逗号分隔）| compare/detect_anomaly 使用 |
| `--local-path` | 本地 PDF 文件路径 | import 操作必填 |
| `--output` | 输出格式: json, markdown | json |

## 分析输出示例

### 财务指标分析

```json
{
  "symbol": "600519",
  "year": 2023,
  "profitability": {
    "roe": 0.31,
    "roa": 0.25,
    "gross_margin": 0.91,
    "net_margin": 0.52,
    "ebitda": 75600000000
  },
  "solvency": {
    "debt_ratio": 0.28,
    "current_ratio": 4.5,
    "quick_ratio": 3.8,
    "interest_coverage": 125.6
  },
  "growth": {
    "revenue_cagr_3y": 0.15,
    "profit_growth": 0.18,
    "rd_ratio": 0.02
  }
}
```

### 异常检测结果

```json
{
  "symbol": "600519",
  "anomalies": [
    {
      "type": "现金流预警",
      "severity": "high",
      "description": "净利润高但经营现金流持续为负",
      "detail": "近3年净利润均为正，但经营现金流连续为负"
    }
  ]
}
```

## 数据存储

年报 PDF 默认保存在：
```
~/.openclaw/workspace/annual-reports/{symbol}/{year}.pdf
```

解析后的数据保存在：
```
~/.openclaw/workspace/annual-reports/{symbol}/{year}_parsed.json
```

## 注意事项

1. 年报下载依赖公开渠道，部分网站可能有反爬机制，建议手动下载后导入
2. PDF 解析准确率依赖年报格式规范程度
3. 财务指标计算基于标准会计准则
4. 异常检测仅供参考，不构成投资建议
