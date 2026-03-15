#!/usr/bin/env python3
"""
股票持仓分析脚本
分析持仓股票的技术面，给出买入/卖出/调仓建议
支持 A股 和 港股
"""

import sys
import os
import json
import subprocess
from datetime import datetime, timedelta

# 持仓数据 - 从 portfolio.txt 读取
def load_portfolio():
    """从 portfolio.txt 加载持仓数据"""
    portfolio_file = os.path.join(os.path.dirname(__file__), '..', 'portfolio.txt')
    if os.path.exists(portfolio_file):
        data = []
        with open(portfolio_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines[1:]:  # 跳过标题行
                parts = line.strip().split('\t')
                if len(parts) >= 5:
                    data.append({
                        "name": parts[0],
                        "market_value": float(parts[1]) if parts[1] else 0,
                        "position_pct": float(parts[2].replace('%', '')) if parts[2] else 0,
                        "code": parts[3],
                        "market": parts[4],
                    })
        return data
    return []

PORTFOLIO_DATA = load_portfolio()

# 市场判断
def get_market(code: str) -> str:
    """判断市场: HK(港股), SH(沪市), SZ(深市)"""
    # 港股: 5位数字以0开头
    if len(code) == 5 and code.startswith('0'):
        return 'HK'
    # 沪市: 6位数字以6开头
    if len(code) == 6 and code.startswith('6'):
        return 'SH'
    # 深市: 其他6位数字
    if len(code) == 6:
        return 'SZ'
    return 'SZ'


def fetch_stock_data(code: str, market: str) -> dict:
    """使用 stock_query.py 获取股票数据"""
    # 使用绝对路径
    stock_query_path = '/home/robot/.openclaw/workspace/skills/stock-data/stock_query.py'
    
    # 备用路径
    alt_path = '/home/robot/agi/CLAW_DATA/ws/skills/stock-data/stock_query.py'
    
    if os.path.exists(stock_query_path):
        query_path = stock_query_path
    elif os.path.exists(alt_path):
        query_path = alt_path
    else:
        return None
    
    # 转换市场标识
    market_map = {'HK': 'hk', 'SH': 'cn', 'SZ': 'cn'}
    market_arg = market_map.get(market, 'cn')
    
    try:
        # 获取实时行情
        result = subprocess.run(
            ['python3', query_path, '--type', 'realtime', '--symbol', code, '--market', market_arg],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode != 0:
            return None
        
        realtime = json.loads(result.stdout)
        if 'error' in realtime:
            return None
        
        # 获取历史数据
        result = subprocess.run(
            ['python3', query_path, '--type', 'history', '--symbol', code, '--market', market_arg, '--days', '30'],
            capture_output=True, text=True, timeout=15
        )
        
        history = []
        if result.returncode == 0:
            hist_data = json.loads(result.stdout)
            history = hist_data.get('data', [])
        
        return {
            'realtime': realtime,
            'history': history
        }
    except Exception as e:
        print(f"获取数据失败 {code}: {e}", file=sys.stderr)
        return None


def calculate_ma(data: list, period: int) -> float:
    """计算MA"""
    if len(data) < period:
        return 0
    closes = [d['close'] for d in data[-period:]]
    return sum(closes) / period


def calculate_rsi(data: list, period: int = 14) -> float:
    """计算RSI"""
    if len(data) < period + 1:
        return 50
    
    closes = [d['close'] for d in data]
    gains = []
    losses = []
    
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        if diff > 0:
            gains.append(diff)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(diff))
    
    if len(gains) < period:
        return 50
    
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    
    if avg_loss == 0:
        return 100
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def analyze_stock(code: str, market: str) -> dict:
    """分析单只股票"""
    data = fetch_stock_data(code, market)
    
    if not data or not data.get('realtime') or not data.get('history'):
        return None
    
    realtime = data['realtime']
    history = data['history']
    
    ma5 = calculate_ma(history, 5)
    ma10 = calculate_ma(history, 10)
    ma20 = calculate_ma(history, 20)
    rsi = calculate_rsi(history, 14)
    
    # 计算涨跌幅
    price = realtime.get('price', 0)
    prev_close = realtime.get('prev_close', price)
    if prev_close > 0:
        change = (price - prev_close) / prev_close * 100
    else:
        change = 0
    
    return {
        'realtime': realtime,
        'ma5': ma5,
        'ma10': ma10,
        'ma20': ma20,
        'rsi': rsi,
        'change': change,
        'history': history,
    }


def generate_signal(analysis: dict) -> tuple:
    """生成交易信号"""
    if not analysis:
        return "无法分析", "数据获取失败"
    
    price = analysis['realtime'].get('price', 0)
    ma5 = analysis['ma5']
    ma10 = analysis['ma10']
    ma20 = analysis['ma20']
    rsi = analysis['rsi']
    change = analysis['change']
    
    # 均线多头排列
    if ma5 > ma10 > ma20 and price > ma5:
        return "📈 买入", "均线多头排列，上涨趋势"
    # 均线空头排列
    elif ma5 < ma10 < ma20 and price < ma5:
        return "📉 卖出", "均线空头排列，下跌趋势"
    # RSI超买
    elif rsi > 75:
        return "⚠️ 卖出", f"RSI超买({rsi:.0f})，注意风险"
    # RSI超卖
    elif rsi < 25:
        return "⚠️ 买入", f"RSI超卖({rsi:.0f})，可能反弹"
    # 放量下跌
    elif change < -5:
        return "⚠️ 观察", "放量下跌，注意风险"
    # 放量上涨
    elif change > 5:
        return "✅ 持有", "放量上涨，趋势良好"
    else:
        return "💤 持有", "震荡整理"


def generate_report() -> str:
    """生成完整的分析报告"""
    if not PORTFOLIO_DATA:
        return "❌ 未找到持仓数据，请检查 portfolio.txt 文件"
    
    report_lines = []
    report_lines.append("=" * 70)
    report_lines.append(f"📊 股票持仓分析报告 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    report_lines.append("=" * 70)
    
    # 计算总市值
    total_value = sum(h['market_value'] for h in PORTFOLIO_DATA)
    a_shares = [h for h in PORTFOLIO_DATA if h['market'] in ['沪A', '深A']]
    hk_shares = [h for h in PORTFOLIO_DATA if h['market'] == '沪港通']
    
    report_lines.append(f"\n💰 总持仓: ¥{total_value:,.2f} (A股{len(a_shares)}只, 港股{len(hk_shares)}只)")
    
    # 分析每只股票
    buy_list = []
    sell_list = []
    hold_list = []
    fail_list = []
    
    report_lines.append("\n" + "-" * 70)
    
    for holding in PORTFOLIO_DATA:
        code = holding['code']
        market = get_market(code)
        
        analysis = analyze_stock(code, market)
        
        if not analysis:
            fail_list.append(holding['name'])
            report_lines.append(f"\n❌ {holding['name']} ({code}): 数据获取失败")
            continue
        
        signal, reason = generate_signal(analysis)
        rt = analysis['realtime']
        
        # 按信号分类
        item = {
            'name': holding['name'],
            'code': code,
            'market': holding['market'],
            'pct': holding['position_pct'],
            'price': rt.get('price', 0),
            'change': analysis['change'],
            'rsi': analysis['rsi'],
            'signal': signal,
            'reason': reason,
        }
        
        if "买入" in signal:
            buy_list.append(item)
        elif "卖出" in signal:
            sell_list.append(item)
        else:
            hold_list.append(item)
        
        # 格式化输出
        pct_str = f"{holding['position_pct']:.1f}%"
        change_str = f"{analysis['change']:+.2f}%"
        rsi_str = f"RSI:{analysis['rsi']:.0f}"
        market_str = "港股" if market == 'HK' else "A股"
        
        report_lines.append(f"\n{holding['name']} ({market_str}, {pct_str})")
        report_lines.append(f"  代码: {code}")
        report_lines.append(f"  价格: ¥{rt.get('price', 0):.2f} {change_str} | {rsi_str}")
        report_lines.append(f"  均线: MA5={analysis['ma5']:.2f} MA10={analysis['ma10']:.2f} MA20={analysis['ma20']:.2f}")
        report_lines.append(f"  信号: {signal} - {reason}")
    
    # 输出建议
    report_lines.append("\n" + "=" * 70)
    report_lines.append("🎯 操作建议")
    report_lines.append("=" * 70)
    
    report_lines.append("\n🟢 【建议买入】")
    if buy_list:
        for item in buy_list:
            report_lines.append(f"  • {item['name']} ({item['code']}, {item['pct']:.1f}%) - {item['reason']}")
    else:
        report_lines.append("  (当前无)")
    
    report_lines.append("\n🔴 【建议卖出】")
    if sell_list:
        for item in sell_list:
            report_lines.append(f"  • {item['name']} ({item['code']}, {item['pct']:.1f}%) - {item['reason']}")
    else:
        report_lines.append("  (当前无)")
    
    report_lines.append("\n🟡 【持有观察】")
    # 重仓股优先显示
    hold_sorted = sorted(hold_list, key=lambda x: x['pct'], reverse=True)
    for item in hold_sorted[:10]:
        report_lines.append(f"  • {item['name']} ({item['code']}, {item['pct']:.1f}%) - {item['reason']}")
    
    # 港股专门分析
    if hk_shares:
        report_lines.append("\n" + "=" * 70)
        report_lines.append("🇭🇰 港股通持仓专项分析")
        report_lines.append("=" * 70)
        
        hk_items = [item for item in buy_list + sell_list + hold_list if item['market'] == '沪港通']
        for item in hk_items:
            report_lines.append(f"\n  {item['name']} ({item['code']})")
            report_lines.append(f"    仓位: {item['pct']:.1f}% | 信号: {item['signal']}")
            report_lines.append(f"    现价: ¥{item['price']:.2f} | 涨跌: {item['change']:+.2f}%")
    
    report_lines.append("\n" + "=" * 70)
    report_lines.append("⚠️ 风险提示: 此分析仅供参考，不构成投资建议")
    report_lines.append("=" * 70)
    
    return "\n".join(report_lines)


if __name__ == "__main__":
    print(generate_report())
