---
name: stock-data
description: 获取股票市场数据的技能。支持A股、港股的实时行情、历史数据、财务指标查询。使用东方财富和腾讯财经API获取数据，中国大陆可直接访问。
---

# 股票数据查询技能

## 概述

获取股票市场数据，支持：
- **A股**（沪深两市）- 东方财富数据源
- **港股** - 腾讯财经数据源
- 实时行情
- 历史K线数据
- 股票基本信息
- 行业板块数据

## 使用方法

### 1. 查询A股实时行情

```bash
python3 /skills/stock-data/stock_query.py --type realtime --symbol 600519
```

### 2. 查询港股实时行情

```bash
python3 /skills/stock-data/stock_query.py --type realtime --symbol 00700 --market hk
```

### 3. 查询历史K线数据

```bash
python3 /skills/stock-data/stock_query.py --type history --symbol 600519 --days 30
```

### 4. 查询股票信息

```bash
python3 /skills/stock-data/stock_query.py --type info --symbol 600519
```

### 5. 查询板块行情

```bash
python3 /skills/stock-data/stock_query.py --type sector
```

## 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--type` | 查询类型: realtime, history, info, sector | realtime |
| `--symbol` | 股票代码 | 必填 |
| `--market` | 市场: cn(A股), hk(港股) | cn |
| `--days` | 历史天数 | 30 |

## 示例输出

### A股实时行情

```json
{
  "symbol": "600519",
  "name": "贵州茅台",
  "price": 1392.0,
  "high": 1403.95,
  "low": 1391.01,
  "change": 0.94,
  "change_pct": 0.07,
  "volume": 27586,
  "source": "东方财富"
}
```

### 港股实时行情

```json
{
  "symbol": "00700",
  "name": "腾讯控股",
  "price": 546.5,
  "change": -5.5,
  "change_pct": -1.0,
  "volume": 19663840,
  "source": "腾讯财经"
}
```

## 常用股票代码参考

### A股热门
| 代码 | 名称 |
|------|------|
| 600519 | 贵州茅台 |
| 000858 | 五粮液 |
| 601318 | 中国平安 |
| 000001 | 平安银行 |
| 600036 | 招商银行 |

### 港股热门
| 代码 | 名称 |
|------|------|
| 00700 | 腾讯控股 |
| 09988 | 阿里巴巴 |
| 03690 | 美团 |
| 00941 | 中国移动 |

## 注意事项

1. 数据来源于公开API，免费使用
2. 数据仅供参考，不构成投资建议
3. A股历史数据和详情使用东方财富接口
4. 港股使用腾讯财经接口
5. 美股暂不支持（需要海外API）
