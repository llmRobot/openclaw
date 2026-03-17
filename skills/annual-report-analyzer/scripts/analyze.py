#!/usr/bin/env python3
"""
年报财务分析脚本 - 完整版
获取A股上市公司财务指标数据，识别财务风险，生成分析报告

功能：
- 五维度财务指标分析（每股、盈利、偿债、运营、成长）
- 现金流质量分析（净现比、收现比）
- 财务造假信号检测
- 风险预警报告生成

用法:
    python3 analyze.py <股票代码> [--periods N] [--json] [--key-metrics] [--risk-report] [--output FILE]
"""

import argparse
import json
import re
import sys
import urllib.request
import urllib.error
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field


@dataclass
class RiskSignal:
    """风险信号"""
    name: str
    value: str
    risk_level: str  # 低/中/高
    description: str


@dataclass 
class FinancialData:
    """财务数据结构"""
    symbol: str = ""
    name: str = ""
    periods: List[str] = field(default_factory=list)
    metrics: Dict[str, Dict[str, List[Optional[str]]]] = field(default_factory=dict)
    risk_signals: List[RiskSignal] = field(default_factory=list)
    health_score: int = 0


# ==================== 数据获取 ====================

def fetch_financial_data(symbol: str) -> str:
    """从新浪财经获取财务数据HTML"""
    url = f"https://vip.stock.finance.sina.com.cn/corp/go.php/vFD_FinancialGuideLine/stockid/{symbol}/displaytype/4.phtml"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.read().decode('gbk', errors='ignore')
    except urllib.error.URLError as e:
        raise RuntimeError(f"网络请求失败: {e}")


def fetch_stock_info(symbol: str) -> Tuple[str, float, float]:
    """获取股票名称和实时价格"""
    url = f"https://push2.eastmoney.com/api/qt/stock/get?secid=0.{symbol}&fields=f58,f43,f44"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))
            if 'data' in result and result['data']:
                d = result['data']
                name = d.get('f58', symbol)
                price = d.get('f43', 0) / 100 if d.get('f43') else 0
                change = d.get('f44', 0) / 100 if d.get('f44') else 0
                return name, price, change
    except:
        pass
    return symbol, 0, 0


def parse_table_rows(html: str) -> List[tuple]:
    """解析HTML表格数据"""
    pattern = r'<tr><td[^>]*>(.*?)</td><td>(.*?)</td><td>(.*?)</td><td>(.*?)</td><td>(.*?)</td></tr>'
    return re.findall(pattern, html, re.DOTALL)


def extract_metric_name(cell: str) -> str:
    """提取指标名称，去除HTML标签"""
    return re.sub(r'<[^>]+>', '', cell).strip()


# ==================== 数据解析 ====================

def parse_financial_data(html: str, periods: int = 4) -> FinancialData:
    """解析财务数据"""
    rows = parse_table_rows(html)
    
    data = FinancialData()
    
    # 指标分类定义
    metric_categories = {
        '每股指标': ['每股收益', '每股净资产', '每股经营', '每股未分配', '每股资本'],
        '盈利能力': ['净资产收益率', '毛利率', '净利率', '营业利润率', '总资产报酬率', 'ROE'],
        '偿债能力': ['资产负债率', '流动比率', '速动比率', '利息保障', '有息负债'],
        '运营能力': ['周转率', '周转天数'],
        '成长能力': ['增长率', '增长比']
    }
    
    data.metrics = {cat: {} for cat in metric_categories.keys()}
    
    for row in rows:
        name = extract_metric_name(row[0])
        values = [row[1], row[2], row[3], row[4]]
        values = [v if v != '--' else None for v in values]
        
        # 提取报告期
        if '报告日期' in name:
            data.periods = [v for v in values[:periods] if v]
            continue
        
        # 分类指标
        for category, keywords in metric_categories.items():
            if any(kw in name for kw in keywords):
                clean_name = name.replace(category, '').strip()
                if clean_name not in data.metrics[category]:
                    data.metrics[category][clean_name] = values[:periods]
                break
    
    return data


# ==================== 风险分析 ====================

def safe_float(value: Optional[str]) -> Optional[float]:
    """安全转换为浮点数"""
    if value is None or value == '':
        return None
    try:
        return float(value)
    except ValueError:
        return None


def analyze_cash_flow_quality(data: FinancialData) -> List[RiskSignal]:
    """分析现金流质量"""
    signals = []
    
    eps = data.metrics.get('每股指标', {}).get('摊薄每股收益(元)', [None])[0]
    cfps = data.metrics.get('每股指标', {}).get('每股经营性现金流(元)', [None])[0]
    
    eps_val = safe_float(eps)
    cfps_val = safe_float(cfps)
    
    if eps_val and cfps_val and eps_val > 0:
        net_cash_ratio = cfps_val / eps_val
        if net_cash_ratio >= 1.0:
            signals.append(RiskSignal('净现比', f'{net_cash_ratio:.2f}', '低',
                f'净现比{net_cash_ratio:.2f}>1，利润有现金支撑，质量高'))
        elif net_cash_ratio >= 0.7:
            signals.append(RiskSignal('净现比', f'{net_cash_ratio:.2f}', '中',
                f'净现比{net_cash_ratio:.2f}，利润含金量一般，需关注'))
        else:
            signals.append(RiskSignal('净现比', f'{net_cash_ratio:.2f}', '高',
                f'净现比{net_cash_ratio:.2f}<0.7，利润含金量低，可能存在虚增'))
    
    return signals


def analyze_profitability(data: FinancialData) -> List[RiskSignal]:
    """分析盈利能力"""
    signals = []
    
    roe = data.metrics.get('盈利能力', {}).get('净资产收益率(%)', [None])
    roe_val = safe_float(roe[0]) if roe else None
    
    if roe_val is not None:
        if roe_val >= 15:
            signals.append(RiskSignal('ROE', f'{roe_val:.1f}%', '低',
                f'ROE {roe_val:.1f}%>=15%，盈利能力优秀'))
        elif roe_val >= 8:
            signals.append(RiskSignal('ROE', f'{roe_val:.1f}%', '中',
                f'ROE {roe_val:.1f}%，盈利能力一般'))
        else:
            signals.append(RiskSignal('ROE', f'{roe_val:.1f}%', '高',
                f'ROE {roe_val:.1f}%<8%，盈利能力弱'))
    
    return signals


def analyze_solvency(data: FinancialData) -> List[RiskSignal]:
    """分析偿债能力"""
    signals = []
    
    debt_ratio = data.metrics.get('偿债能力', {}).get('资产负债率(%)', [None])
    debt_val = safe_float(debt_ratio[0]) if debt_ratio else None
    
    if debt_val is not None:
        if debt_val <= 60:
            signals.append(RiskSignal('资产负债率', f'{debt_val:.1f}%', '低',
                f'资产负债率{debt_val:.1f}%<=60%，财务结构稳健'))
        elif debt_val <= 70:
            signals.append(RiskSignal('资产负债率', f'{debt_val:.1f}%', '中',
                f'资产负债率{debt_val:.1f}%，需关注债务压力'))
        else:
            signals.append(RiskSignal('资产负债率', f'{debt_val:.1f}%', '高',
                f'资产负债率{debt_val:.1f}%>70%，杠杆风险高'))
    
    current_ratio = data.metrics.get('偿债能力', {}).get('流动比率', [None])
    cr_val = safe_float(current_ratio[0]) if current_ratio else None
    
    if cr_val is not None:
        if cr_val >= 1.5:
            signals.append(RiskSignal('流动比率', f'{cr_val:.2f}', '低',
                f'流动比率{cr_val:.2f}>=1.5，短期偿债能力良好'))
        else:
            signals.append(RiskSignal('流动比率', f'{cr_val:.2f}', '高',
                f'流动比率{cr_val:.2f}<1.5，短期偿债压力大'))
    
    return signals


def analyze_growth(data: FinancialData) -> List[RiskSignal]:
    """分析成长能力"""
    signals = []
    
    profit_growth = data.metrics.get('成长能力', {}).get('净利润增长率(%)', [None])
    pg_val = safe_float(profit_growth[0]) if profit_growth else None
    
    if pg_val is not None:
        if pg_val > 20:
            signals.append(RiskSignal('净利润增长率', f'{pg_val:.1f}%', '低',
                f'净利润增长{pg_val:.1f}%>20%，高增长'))
        elif pg_val > 0:
            signals.append(RiskSignal('净利润增长率', f'{pg_val:.1f}%', '中',
                f'净利润增长{pg_val:.1f}%，稳定增长'))
        else:
            signals.append(RiskSignal('净利润增长率', f'{pg_val:.1f}%', '高',
                f'净利润增长{pg_val:.1f}%<0，业绩下滑'))
    
    revenue_growth = data.metrics.get('成长能力', {}).get('主营业务收入增长率(%)', [None])
    rg_val = safe_float(revenue_growth[0]) if revenue_growth else None
    
    if rg_val is not None:
        if rg_val < 0:
            signals.append(RiskSignal('营收增长率', f'{rg_val:.1f}%', '高',
                f'营收增长{rg_val:.1f}%<0，主营业务收缩'))
    
    return signals


def analyze_operation(data: FinancialData) -> List[RiskSignal]:
    """分析运营能力"""
    signals = []
    
    ar_turnover = data.metrics.get('运营能力', {}).get('应收账款周转率(次)', [None])
    ar_val = safe_float(ar_turnover[0]) if ar_turnover else None
    
    if ar_val is not None and ar_val < 3:
        signals.append(RiskSignal('应收账款周转率', f'{ar_val:.1f}次', '中',
            f'应收账款周转率{ar_val:.1f}次较低，回款周期长'))
    
    inv_turnover = data.metrics.get('运营能力', {}).get('存货周转率(次)', [None])
    inv_val = safe_float(inv_turnover[0]) if inv_turnover else None
    
    if inv_val is not None and inv_val < 1:
        signals.append(RiskSignal('存货周转率', f'{inv_val:.2f}次', '中',
            f'存货周转率{inv_val:.2f}次较低，库存周转慢'))
    
    return signals


def run_risk_analysis(data: FinancialData) -> None:
    """运行完整风险分析"""
    signals = []
    signals.extend(analyze_cash_flow_quality(data))
    signals.extend(analyze_profitability(data))
    signals.extend(analyze_solvency(data))
    signals.extend(analyze_growth(data))
    signals.extend(analyze_operation(data))
    data.risk_signals = signals
    
    # 计算健康度评分
    score = 100
    for signal in signals:
        if signal.risk_level == '高':
            score -= 15
        elif signal.risk_level == '中':
            score -= 5
    data.health_score = max(0, min(100, score))


# ==================== 报告生成 ====================

def format_value(value: Optional[str], suffix: str = '') -> str:
    """格式化数值显示"""
    if value is None or value == '':
        return 'N/A'
    try:
        num = float(value)
        if abs(num) >= 1e8:
            return f"{num/1e8:.2f}亿{suffix}"
        elif abs(num) >= 1e4:
            return f"{num/1e4:.2f}万{suffix}"
        else:
            formatted = f"{num:.4f}".rstrip('0').rstrip('.')
            return formatted + suffix if suffix else formatted
    except ValueError:
        return value + suffix if suffix else value


def generate_report(data: FinancialData, key_only: bool = False) -> str:
    """生成文本报告"""
    lines = []
    lines.append("=" * 70)
    lines.append(f"{data.name}({data.symbol}) 财务分析报告")
    lines.append("=" * 70)
    lines.append("")
    
    periods = data.periods or ['N/A', 'N/A', 'N/A', 'N/A']
    
    # 关键指标优先显示
    priority_categories = ['每股指标', '盈利能力', '偿债能力', '成长能力']
    
    for category in priority_categories:
        if category not in data.metrics or not data.metrics[category]:
            continue
            
        lines.append(f"【{category}】")
        lines.append("-" * 70)
        lines.append(f"{'指标':<22} " + " ".join(f"{p:<12}" for p in periods[:4]))
        lines.append("-" * 70)
        
        for metric_name, values in data.metrics[category].items():
            if key_only and category == '运营能力':
                continue
            display_name = metric_name[:20] if len(metric_name) > 20 else metric_name
            formatted_values = [format_value(v) for v in values]
            lines.append(f"{display_name:<22} " + " ".join(f"{v:<12}" for v in formatted_values))
        
        lines.append("")
    
    return "\n".join(lines)


def generate_risk_report(data: FinancialData) -> str:
    """生成风险预警报告"""
    lines = []
    lines.append("=" * 70)
    lines.append(f"{data.name}({data.symbol}) 财务风险预警报告")
    lines.append("=" * 70)
    lines.append("")
    
    # 风险等级判定
    high_risks = [s for s in data.risk_signals if s.risk_level == '高']
    mid_risks = [s for s in data.risk_signals if s.risk_level == '中']
    
    if high_risks:
        risk_emoji = "🔴"
        risk_level = "高风险"
    elif mid_risks:
        risk_emoji = "🟡"
        risk_level = "中等风险"
    else:
        risk_emoji = "🟢"
        risk_level = "低风险"
    
    lines.append(f"【风险等级】：{risk_level} {risk_emoji}")
    lines.append(f"【健康度评分】：{data.health_score}/100")
    lines.append("")
    
    # 风险信号详情
    if data.risk_signals:
        lines.append("【风险信号扫描】")
        lines.append("-" * 70)
        lines.append(f"{'指标':<20} {'当前值':<12} {'风险等级':<10} {'说明'}")
        lines.append("-" * 70)
        
        for signal in data.risk_signals:
            level_mark = "⚠️" if signal.risk_level == '高' else ("⚡" if signal.risk_level == '中' else "✅")
            lines.append(f"{signal.name:<20} {signal.value:<12} {signal.risk_level:<8} {level_mark} {signal.description}")
        
        lines.append("")
    
    # 风险总结
    lines.append("【综合评估】")
    lines.append("-" * 70)
    
    positives = [s for s in data.risk_signals if s.risk_level == '低']
    negatives = [s for s in data.risk_signals if s.risk_level in ['中', '高']]
    
    if positives:
        lines.append("有利因素：")
        for s in positives[:5]:
            lines.append(f"  ✅ {s.description}")
    
    if negatives:
        lines.append("")
        lines.append("风险因素：")
        for s in negatives[:5]:
            mark = "⚠️" if s.risk_level == '高' else "⚡"
            lines.append(f"  {mark} {s.description}")
    
    lines.append("")
    lines.append("注: 风险评估基于财务指标分析，不构成投资建议")
    
    return "\n".join(lines)


def generate_summary(data: FinancialData) -> str:
    """生成财务分析摘要"""
    lines = []
    lines.append("=" * 70)
    lines.append(f"{data.name}({data.symbol}) 财务分析摘要")
    lines.append("=" * 70)
    
    periods = data.periods or ['N/A']
    lines.append(f"报告期: {periods[0] if periods else 'N/A'}")
    lines.append("")
    lines.append("【关键指标】")
    
    eps = data.metrics.get('每股指标', {}).get('摊薄每股收益(元)', [None])[0]
    bvps = data.metrics.get('每股指标', {}).get('每股净资产_调整后(元)', [None])[0]
    roe = data.metrics.get('盈利能力', {}).get('净资产收益率(%)', [None])[0]
    pg = data.metrics.get('成长能力', {}).get('净利润增长率(%)', [None])[0]
    
    if eps: lines.append(f"  每股收益(EPS): {format_value(eps)}元")
    if bvps: lines.append(f"  每股净资产: {format_value(bvps)}元")
    if roe: lines.append(f"  净资产收益率(ROE): {format_value(roe)}%")
    if pg: lines.append(f"  净利润增长率: {format_value(pg)}%")
    
    lines.append("")
    lines.append("【分析要点】")
    
    # 基于风险信号生成要点
    for signal in data.risk_signals[:3]:
        mark = "⚠️" if signal.risk_level == '高' else ("⚡" if signal.risk_level == '中' else "✅")
        lines.append(f"  {mark} {signal.description}")
    
    lines.append("")
    lines.append("注: 数据来源于公开财务报表，仅供参考")
    
    return "\n".join(lines)


# ==================== 主程序 ====================

def main():
    parser = argparse.ArgumentParser(description='上市公司年报财务分析')
    parser.add_argument('symbol', help='股票代码(6位数字)')
    parser.add_argument('--periods', type=int, default=4, help='报告期数量(默认4)')
    parser.add_argument('--json', action='store_true', help='JSON格式输出')
    parser.add_argument('--key-metrics', action='store_true', help='仅输出关键指标')
    parser.add_argument('--summary', action='store_true', help='仅输出摘要')
    parser.add_argument('--risk-report', action='store_true', help='生成风险预警报告')
    parser.add_argument('--output', help='输出文件路径')
    
    args = parser.parse_args()
    symbol = args.symbol.zfill(6)
    
    try:
        # 获取股票信息
        name, price, change = fetch_stock_info(symbol)
        
        # 获取并解析财务数据
        html = fetch_financial_data(symbol)
        data = parse_financial_data(html, args.periods)
        data.symbol = symbol
        data.name = name
        
        # 运行风险分析
        run_risk_analysis(data)
        
        # 生成输出
        if args.json:
            output_data = {
                'symbol': symbol,
                'name': name,
                'periods': data.periods,
                'metrics': data.metrics,
                'risk_signals': [{'name': s.name, 'value': s.value, 'level': s.risk_level, 'desc': s.description} for s in data.risk_signals],
                'health_score': data.health_score
            }
            output = json.dumps(output_data, ensure_ascii=False, indent=2)
        elif args.risk_report:
            output = generate_risk_report(data)
        elif args.summary:
            output = generate_summary(data)
        else:
            output = generate_report(data, args.key_metrics)
        
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output)
            print(f"报告已保存到: {args.output}")
        else:
            print(output)
            
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
