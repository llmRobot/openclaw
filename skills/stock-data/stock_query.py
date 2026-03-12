#!/usr/bin/env python3
"""
股票数据查询工具 (中国大陆可用)
使用新浪财经/腾讯财经 API 获取股票市场数据
支持 A股、港股、美股
"""

import argparse
import json
import sys
import re
import urllib.request
import urllib.error
from datetime import datetime, timedelta

# 尝试导入 requests，没有就用 urllib
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


def http_get(url: str, headers: dict = None, timeout: int = 10) -> str:
    """HTTP GET 请求"""
    default_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Charset": "GBK,utf-8;q=0.7,*;q=0.3",
    }
    if headers:
        default_headers.update(headers)
    
    if HAS_REQUESTS:
        resp = requests.get(url, headers=default_headers, timeout=timeout)
        # 尝试多种编码
        for encoding in ['gbk', 'gb2312', 'utf-8']:
            try:
                resp.encoding = encoding
                text = resp.text
                # 检查是否有乱码
                if '�' not in text or encoding == 'utf-8':
                    return text
            except:
                continue
        return resp.text
    else:
        req = urllib.request.Request(url, headers=default_headers)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            content = response.read()
            # 尝试多种编码
            for encoding in ['gbk', 'gb2312', 'utf-8']:
                try:
                    return content.decode(encoding)
                except:
                    continue
            return content.decode('utf-8', errors='ignore')


def get_sina_symbol(symbol: str, market: str = "cn") -> str:
    """转换股票代码为新浪格式"""
    if market == "cn":
        # A股：沪市加sh，深市加sz
        if symbol.startswith("6"):
            return f"sh{symbol}"
        else:
            return f"sz{symbol}"
    elif market == "hk":
        # 港股：hk + 5位数字 (如 hk00700)
        return f"hk{symbol.zfill(5)}"
    elif market == "us":
        # 美股：gb_ 前缀
        return f"gb_{symbol.lower()}"
    return symbol


def get_realtime_quote_sina(symbol: str, market: str = "cn") -> dict:
    """使用新浪财经获取实时行情"""
    try:
        sina_symbol = get_sina_symbol(symbol, market)
        url = f"https://hq.sinajs.cn/list={sina_symbol}"
        
        text = http_get(url)
        
        # 解析返回数据
        # 格式: var hq_str_sh600519="贵州茅台,1800.00,1795.00,1810.50,1820.00,1780.00,1810.50,1810.50,12345,18105000,..."
        match = re.search(r'="([^"]*)"', text)
        if not match:
            return {"error": "数据解析失败", "symbol": symbol}
        
        data = match.group(1).split(',')
        
        if len(data) < 32:
            return {"error": "数据不完整", "symbol": symbol}
        
        if market == "cn":
            return {
                "symbol": symbol,
                "name": data[0],
                "open": float(data[1]) if data[1] else 0,
                "prev_close": float(data[2]) if data[2] else 0,
                "price": float(data[3]) if data[3] else 0,
                "high": float(data[4]) if data[4] else 0,
                "low": float(data[5]) if data[5] else 0,
                "bid": float(data[6]) if data[6] else 0,
                "ask": float(data[7]) if data[7] else 0,
                "volume": int(float(data[8])) if data[8] else 0,
                "amount": float(data[9]) if data[9] else 0,
                "market": "A股",
                "source": "新浪财经",
                "timestamp": datetime.now().isoformat()
            }
        elif market == "hk":
            # 港股使用腾讯接口
            return get_tencent_hk_quote(symbol)
        elif market == "us":
            return {
                "symbol": symbol.upper(),
                "name": data[0],
                "price": float(data[1]) if data[1] else 0,
                "change": float(data[2]) if data[2] else 0,
                "change_pct": float(data[3].replace('%', '')) if data[3] else 0,
                "open": float(data[5]) if data[5] else 0,
                "high": float(data[6]) if data[6] else 0,
                "low": float(data[7]) if data[7] else 0,
                "volume": int(float(data[10])) if data[10] else 0,
                "prev_close": float(data[26]) if data[26] else 0,
                "market": "美股",
                "source": "新浪财经",
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        return {"error": str(e), "symbol": symbol}


def get_tencent_hk_quote(symbol: str) -> dict:
    """使用腾讯接口获取港股实时行情"""
    try:
        # 腾讯港股接口
        hk_symbol = symbol.zfill(5)
        url = f"https://qt.gtimg.cn/q=r_hk{hk_symbol}"
        
        text = http_get(url)
        
        # 解析返回数据
        # 格式: v_r_hk00700="100~腾讯控股~00700~546.500~552.000~550.500~19663840.0~..."
        match = re.search(r'="([^"]*)"', text)
        if not match:
            return {"error": "数据解析失败", "symbol": symbol}
        
        data = match.group(1).split('~')
        
        if len(data) < 35:
            return {"error": "数据不完整", "symbol": symbol, "fields": len(data)}
        
        # 字段索引 (从腾讯返回数据解析)
        # 1: 名称, 2: 代码, 3: 当前价, 4: 最高, 5: 最低?, 6: 成交量
        # 31: 涨跌额, 32: 涨跌幅, 33: 52周高, 34: 52周低
        price = float(data[3]) if data[3] else 0
        change = float(data[31]) if data[31] and data[31] not in ['-', ''] else 0
        change_pct = float(data[32]) if data[32] and data[32] not in ['-', ''] else 0
        
        return {
            "symbol": symbol,
            "name": data[1],
            "price": price,
            "high": float(data[4]) if data[4] else 0,
            "low": float(data[5]) if data[5] else 0,
            "volume": int(float(data[6])) if data[6] else 0,
            "prev_close": price - change,
            "change": change,
            "change_pct": change_pct,
            "52week_high": float(data[33]) if data[33] and data[33] not in ['-', ''] else 0,
            "52week_low": float(data[34]) if data[34] and data[34] not in ['-', ''] else 0,
            "market": "港股",
            "source": "腾讯财经",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e), "symbol": symbol}


def get_eastmoney_quote(symbol: str) -> dict:
    """使用东方财富获取A股实时行情"""
    try:
        # 判断市场
        if symbol.startswith("6"):
            secid = f"1.{symbol}"
        else:
            secid = f"0.{symbol}"
        
        url = f"https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields=f43,f44,f45,f46,f47,f48,f50,f51,f52,f55,f57,f58,f60,f170,f171"
        
        text = http_get(url)
        data = json.loads(text)
        
        if not data.get("data"):
            return {"error": "数据获取失败", "symbol": symbol}
        
        d = data["data"]
        
        return {
            "symbol": symbol,
            "name": d.get("f58", ""),
            "price": d.get("f43", 0) / 100 if d.get("f43") else 0,
            "high": d.get("f44", 0) / 100 if d.get("f44") else 0,
            "low": d.get("f45", 0) / 100 if d.get("f45") else 0,
            "open": d.get("f46", 0) / 100 if d.get("f46") else 0,
            "volume": d.get("f47", 0),
            "amount": d.get("f48", 0),
            "change": d.get("f50", 0) / 100 if d.get("f50") else 0,
            "change_pct": d.get("f51", 0) / 100 if d.get("f51") else 0,
            "prev_close": d.get("f60", 0) / 100 if d.get("f60") else 0,
            "market_cap": d.get("f116", 0),
            "pe_ratio": d.get("f170", 0) / 100 if d.get("f170") else 0,
            "market": "A股",
            "source": "东方财富",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e), "symbol": symbol}


def get_history_data_eastmoney(symbol: str, days: int = 30) -> dict:
    """使用东方财富获取历史K线数据"""
    try:
        # 判断市场
        if symbol.startswith("6"):
            secid = f"1.{symbol}"
        else:
            secid = f"0.{symbol}"
        
        url = f"https://push2his.eastmoney.com/api/qt/stock/kline/get?secid={secid}&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57&klt=101&fqt=1&end=20500101&lmt={days}"
        
        text = http_get(url)
        data = json.loads(text)
        
        if not data.get("data") or not data["data"].get("klines"):
            return {"error": "数据获取失败", "symbol": symbol}
        
        klines = data["data"]["klines"]
        records = []
        
        for line in klines:
            parts = line.split(',')
            records.append({
                "date": parts[0],
                "open": float(parts[1]),
                "close": float(parts[2]),
                "high": float(parts[3]),
                "low": float(parts[4]),
                "volume": int(float(parts[5])),
                "amount": float(parts[6])
            })
        
        return {
            "symbol": symbol,
            "period": "daily",
            "days": len(records),
            "data": records,
            "source": "东方财富",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e), "symbol": symbol}


def get_stock_info_eastmoney(symbol: str) -> dict:
    """使用东方财富获取股票基本信息"""
    try:
        # 判断市场
        if symbol.startswith("6"):
            secid = f"1.{symbol}"
        else:
            secid = f"0.{symbol}"
        
        url = f"https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields=f57,f58,f84,f85,f116,f117,f162,f167,f92,f173,f187,f105,f190"
        
        text = http_get(url)
        data = json.loads(text)
        
        if not data.get("data"):
            return {"error": "数据获取失败", "symbol": symbol}
        
        d = data["data"]
        
        return {
            "symbol": symbol,
            "name": d.get("f58", ""),
            "market_cap": d.get("f116", 0),
            "circulating_cap": d.get("f117", 0),
            "total_shares": d.get("f84", 0),
            "circulating_shares": d.get("f85", 0),
            "pe_ratio": d.get("f162", 0) / 100 if d.get("f162") else 0,
            "pb_ratio": d.get("f167", 0) / 100 if d.get("f167") else 0,
            "dividend_yield": d.get("f187", 0) / 100 if d.get("f187") else 0,
            "52week_high": d.get("f173", 0) / 100 if d.get("f173") else 0,
            "52week_low": d.get("f105", 0) / 100 if d.get("f105") else 0,
            "market": "A股",
            "source": "东方财富",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e), "symbol": symbol}


def get_sector_data() -> dict:
    """获取板块行情"""
    try:
        url = "https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=20&po=1&np=1&fltt=2&invt=2&fid=f3&fs=m:90+t:2&fields=f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87,f204,f205,f124,f1,f13"
        
        text = http_get(url)
        data = json.loads(text)
        
        if not data.get("data") or not data["data"].get("diff"):
            return {"error": "数据获取失败"}
        
        records = []
        for item in data["data"]["diff"]:
            records.append({
                "code": item.get("f12", ""),
                "name": item.get("f14", ""),
                "price": item.get("f2", 0) / 100 if item.get("f2") else 0,
                "change_pct": item.get("f3", 0) / 100 if item.get("f3") else 0,
            })
        
        return {
            "type": "行业板块",
            "data": records,
            "source": "东方财富",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}


def get_realtime_quote(symbol: str, market: str = "cn") -> dict:
    """获取实时行情"""
    if market == "cn":
        # A股优先使用东方财富
        result = get_eastmoney_quote(symbol)
        if "error" not in result:
            return result
        # 回退到新浪
        return get_realtime_quote_sina(symbol, market)
    elif market == "hk":
        # 港股使用腾讯接口
        return get_tencent_hk_quote(symbol)
    else:
        # 美股使用新浪接口
        return get_realtime_quote_sina(symbol, market)


def get_history_data(symbol: str, market: str = "cn", period: str = "daily", days: int = 30) -> dict:
    """获取历史K线数据"""
    if market != "cn":
        return {"error": "暂只支持A股历史数据", "symbol": symbol}
    return get_history_data_eastmoney(symbol, days)


def get_stock_info(symbol: str, market: str = "cn") -> dict:
    """获取股票详细信息"""
    if market != "cn":
        return {"error": "暂只支持A股详细信息", "symbol": symbol}
    return get_stock_info_eastmoney(symbol)


def main():
    parser = argparse.ArgumentParser(description="股票数据查询工具")
    parser.add_argument("--type", choices=["realtime", "history", "info", "sector"],
                        default="realtime", help="查询类型")
    parser.add_argument("--symbol", help="股票代码")
    parser.add_argument("--market", choices=["cn", "hk", "us"], default="cn",
                        help="市场: cn(A股), hk(港股), us(美股)")
    parser.add_argument("--period", choices=["daily", "weekly", "monthly"],
                        default="daily", help="K线周期 (目前仅支持 daily)")
    parser.add_argument("--days", type=int, default=30, help="历史天数")
    
    args = parser.parse_args()
    
    if args.type in ["realtime", "history", "info"] and not args.symbol:
        print("Error: --symbol is required for realtime/history/info queries")
        sys.exit(1)
    
    result = {}
    
    if args.type == "realtime":
        result = get_realtime_quote(args.symbol, args.market)
    elif args.type == "history":
        result = get_history_data(args.symbol, args.market, args.period, args.days)
    elif args.type == "info":
        result = get_stock_info(args.symbol, args.market)
    elif args.type == "sector":
        result = get_sector_data()
    
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
