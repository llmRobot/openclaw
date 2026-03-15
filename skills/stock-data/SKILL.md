---
name: stock-data
description: 获取股票市场数据的技能。支持A股、港股的实时行情、历史数据、财务指标查询。使用东方财富和腾讯财经API获取数据，中国大陆可直接访问。
---

# 股票数据查询技能

## 概述

获取股票市场数据，支持：
- **A股**（沪深两市）- 东方财富数据源
- **港股**（港股通股票）- 腾讯财经 + 东方财富数据源
- 实时行情
- 历史K线数据
- 股票基本信息
- 行业板块数据
- **自动市场识别** - 无需指定市场

## 使用方法

### 1. 查询实时行情（自动识别市场）

```bash
# A股 - 贵州茅台（自动识别为A股）
python3 /skills/stock-data/stock_query.py --type realtime --symbol 600519

# 港股 - 美团（自动识别为港股，5位数字以0开头）
python3 /skills/stock-data/stock_query.py --type realtime --symbol 03690

# 港股 - 阿里巴巴
python3 /skills/stock-data/stock_query.py --type realtime --symbol 09988
```

### 2. 查询历史K线数据

```bash
# A股历史数据
python3 /skills/stock-data/stock_query.py --type history --symbol 600519 --days 30

# 港股历史数据
python3 /skills/stock-data/stock_query.py --type history --symbol 03690 --days 30
```

### 3. 查询股票详细信息

```bash
# A股详细信息
python3 /skills/stock-data/stock_query.py --type info --symbol 600519

# 港股详细信息
python3 /skills/stock-data/stock_query.py --type info --symbol 09988
```

### 4. 查询板块行情

```bash
python3 /skills/stock-data/stock_query.py --type sector
```

## 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--type` | 查询类型: realtime, history, info, sector | realtime |
| `--symbol` | 股票代码（支持自动识别市场） | 必填 |
| `--market` | 市场: auto(自动识别), cn(A股), hk(港股), us(美股) | auto |
| `--days` | 历史天数 | 30 |

## 市场自动识别规则

| 代码格式 | 识别市场 | 示例 |
|---------|---------|------|
| `0XXXX` (5位数字，以0开头) | 港股 | 00700, 03690, 09988 |
| `6XXXXX` (6位数字，以6开头) | A股沪市 | 600519 |
| `0XXXXX` (6位数字，以0开头) | A股深市 | 000858 |
| `3XXXXX` (6位数字，以3开头) | A股创业板 | 300750 |
| 字母 | 美股 | AAPL, TSLA |

## 示例输出

### 港股实时行情

```json
{
  "symbol": "03690",
  "name": "美团-W",
  "price": 75.95,
  "high": 76.7,
  "low": 76.0,
  "volume": 18836697,
  "prev_close": 76.7,
  "change": -0.75,
  "change_pct": -0.98,
  "52week_high": 77.4,
  "52week_low": 75.85,
  "market": "港股",
  "source": "腾讯财经"
}
```

### 港股历史数据

```json
{
  "symbol": "09988",
  "name": "阿里巴巴-W",
  "period": "daily",
  "days": 5,
  "data": [
    {
      "date": "2026-03-09",
      "open": 125.2,
      "close": 128.7,
      "high": 129.4,
      "low": 125.1,
      "volume": 102893047
    }
  ],
  "source": "东方财富"
}
```

### A股实时行情

```json
{
  "symbol": "600519",
  "name": "贵州茅台",
  "price": 1413.64,
  "high": 1417.62,
  "low": 1392.0,
  "change": 1.17,
  "change_pct": 1531.2,
  "volume": 33608,
  "market": "A股",
  "source": "东方财富"
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

### 港股通热门
| 代码 | 名称 |
|------|------|
| 00700 | 腾讯控股 |
| 09988 | 阿里巴巴-W |
| 03690 | 美团-W |
| 09999 | 网易-S |
| 01810 | 小米集团-W |
| 00941 | 中国移动 |
| 02318 | 平安好医生 |
| 02015 | 理想汽车-W |
| 09868 | 小鹏汽车-W |
| 09961 | 蔚来-SW |

## 注意事项

1. 数据来源于公开API，免费使用
2. 数据仅供参考，不构成投资建议
3. A股实时数据和历史数据使用东方财富接口
4. 港股实时数据优先使用腾讯接口，历史数据使用东方财富接口
5. 美股暂只支持实时行情（新浪接口）
6. 支持 `HK.XXXXX`、`XXXXX.HK` 等格式自动转换

## 更新日志

| 时间 | 更新内容 |
|------|---------|
| 2026-03-15 | 添加港股历史数据和详细信息支持，添加市场自动识别功能 |
| 2026-03-14 | 初始版本，支持A股和港股实时行情 |
