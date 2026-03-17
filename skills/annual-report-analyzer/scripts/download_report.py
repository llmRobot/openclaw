#!/usr/bin/env python3
"""
上市公司财报PDF下载工具 v2.0
数据来源：巨潮资讯网（cninfo.com.cn）
修复：
  - 使用全文搜索API（/new/fulltextSearch/full）精准获取公告
  - 修复 orgId 自动查询（从巨潮官方获取）
  - 修复 PDF URL 构建逻辑
  - 新增年份过滤、多结果选择
  - 支持深交所/上交所双市场

用法:
    python3 download_report.py 000026                           # 飞亚达最新年报
    python3 download_report.py 002916                           # 深南电路最新年报
    python3 download_report.py 000026 --type annual --year 2025 # 指定年份
    python3 download_report.py 000026 --type semi               # 半年报
    python3 download_report.py 000026 --list                    # 仅列出不下载
    python3 download_report.py 000026 --url <PDF直链> --title <标题>
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime


@dataclass
class FinancialReport:
    title: str
    report_type: str
    year: int
    announce_date: str
    pdf_url: str
    source: str = ""
    org_id: str = ""
    announcement_id: str = ""


REPORT_TYPES = {
    'annual': {
        'name': '年度报告',
        'search_keywords': ['年度报告'],
        'title_must': ['年度报告'],
        'title_exclude': ['摘要', '英文版', '英文年度', '修订', '更正', '半年', '季度', '披露', '说明书'],
    },
    'semi': {
        'name': '半年度报告',
        'search_keywords': ['半年度报告'],
        'title_must': ['半年度报告'],
        'title_exclude': ['摘要', '英文', '修订', '更正', '年度报告'],
    },
    'q1': {
        'name': '第一季度报告',
        'search_keywords': ['第一季度报告', '一季报'],
        'title_must': ['一季报', '一季度报告'],  # 兼容多种标题格式
        'title_exclude': ['摘要', '修订', '更正', '三季'],
    },
    'q3': {
        'name': '第三季度报告',
        'search_keywords': ['第三季度报告', '三季度报告'],
        'title_must': ['三季度报告'],  # 兼容"三季度报告"和"第三季度报告"
        'title_exclude': ['摘要', '修订', '更正', '一季', '一季报'],
    },
}

BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Connection": "keep-alive",
}


# ───────────────────────── 股票 & orgId 查询 ─────────────────────────

def get_stock_info(symbol: str) -> Tuple[str, str]:
    """
    从巨潮资讯查询股票名称和 orgId（最准确来源）
    返回: (股票名称, orgId)
    """
    # 方法1：巨潮快速搜索接口
    url = "https://www.cninfo.com.cn/new/information/top/search/query"
    data = urllib.parse.urlencode(
        {"keyWord": symbol, "maxSecNum": 5, "maxListNum": 0}).encode()
    headers = {**BASE_HEADERS, "Referer": "https://www.cninfo.com.cn/new/index",
               "X-Requested-With": "XMLHttpRequest",
               "Content-Type": "application/x-www-form-urlencoded"}
    try:
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            stocks = result.get('keyBoardList') or []
            for s in stocks:
                if s.get('code') == symbol or s.get('secCode') == symbol:
                    return s.get('zwjc') or s.get('shortName') or symbol, s.get('orgId', '')
            if stocks:
                s = stocks[0]
                return s.get('zwjc') or s.get('shortName') or symbol, s.get('orgId', '')
    except Exception as e:
        pass

    # 方法2：巨潮全文搜索推断 orgId
    try:
        search_url = (
            f"https://www.cninfo.com.cn/new/fulltextSearch/full"
            f"?searchkey={urllib.parse.quote(symbol + ' 年度报告')}"
            f"&sdate=&edate=&isfulltext=false&sortName=time&sortType=desc&pageNum=1"
        )
        headers2 = {**BASE_HEADERS, "Referer": "https://www.cninfo.com.cn/new/fulltextSearch",
                    "X-Requested-With": "XMLHttpRequest"}
        req = urllib.request.Request(search_url, headers=headers2)
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            announcements = (result.get('announcements') or
                             result.get('classifiedAnnouncements') or [])
            if isinstance(announcements, list) and announcements:
                first = announcements[0]
                if isinstance(first, list):
                    first = first[0]
                name = first.get('secName') or first.get(
                    'announcementTitle', symbol)[:4]
                org_id = first.get('orgId', '')
                return name, org_id
    except Exception:
        pass

    # 方法3：fallback — 根据股票代码前缀推断市场
    prefix = symbol[:3]
    if symbol.startswith(("6", "9")):
        org_id = f"9900{symbol}"   # 上交所格式（近似）
    else:
        org_id = f"9999{symbol}"   # 深交所格式（近似）
    return symbol, org_id


# ───────────────────────── 全文搜索 API ─────────────────────────

def search_via_fulltext(stock_name: str, symbol: str, report_type: str, year: int = None) -> List[FinancialReport]:
    """
    使用巨潮全文搜索 API 查询财报公告
    URL: /new/fulltextSearch/full?searchkey=...
    这是用户在浏览器中使用的真实搜索接口，可靠性最高
    """
    type_info = REPORT_TYPES[report_type]
    type_name = type_info['name']
    reports = []

    # 构造搜索词：公司名 + 报告类型（+年份）
    if year:
        searchkey = f"{stock_name} {year}年{type_name}"
    else:
        searchkey = f"{stock_name} {type_name}"

    url = (
        f"https://www.cninfo.com.cn/new/fulltextSearch/full"
        f"?searchkey={urllib.parse.quote(searchkey)}"
        f"&sdate=&edate=&isfulltext=false&sortName=time&sortType=desc&pageNum=1"
    )
    headers = {
        **BASE_HEADERS,
        "Referer": (
            f"https://www.cninfo.com.cn/new/fulltextSearch"
            f"?notautosubmit=&keyWord={urllib.parse.quote(searchkey)}&searchType=0"
        ),
        "X-Requested-With": "XMLHttpRequest",
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read().decode('utf-8'))

        # 结果结构：announcements 可能是 list[dict] 或 list[list[dict]]
        raw = result.get('announcements') or []
        flat = []
        for item in raw:
            if isinstance(item, list):
                flat.extend(item)
            elif isinstance(item, dict):
                flat.append(item)

        for item in flat:
            title = item.get('announcementTitle', '')

            # 标题过滤
            if not any(kw in title for kw in type_info['title_must']):
                continue
            if any(ex in title for ex in type_info['title_exclude']):
                continue

            # 年份提取
            year_match = re.search(r'20\d{2}', title)
            report_year = int(year_match.group()) if year_match else 0
            if year and report_year != year:
                continue

            # 构建 PDF URL
            adjunct_url = item.get('adjunctUrl', '')
            if adjunct_url:
                # adjunctUrl 示例: "finalpage/2026-03-28/1225006760.PDF"
                pdf_url = f"http://static.cninfo.com.cn/{adjunct_url}"
            else:
                announce_time = str(item.get('announcementTime', ''))[:10]
                ann_id = item.get('announcementId', '')
                if announce_time and ann_id:
                    pdf_url = f"http://static.cninfo.com.cn/finalpage/{announce_time}/{ann_id}.PDF"
                else:
                    continue

            # 公告日期
            # 处理时间戳（毫秒转日期）
            raw_time = item.get('announcementTime', 0)
            if raw_time:
                # 毫秒时间戳转日期
                ts = raw_time / 1000 if raw_time > 1000000000000 else raw_time
                announce_date = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
            else:
                announce_date = ''

            reports.append(FinancialReport(
                title=title,
                report_type=report_type,
                year=report_year,
                announce_date=announce_date,
                pdf_url=pdf_url,
                source="巨潮全文搜索",
                org_id=item.get('orgId', ''),
                announcement_id=str(item.get('announcementId', '')),
            ))

    except Exception as e:
        print(f"  [全文搜索] 失败: {e}", file=sys.stderr)

    return reports


# ───────────────────────── 个股公告 API (备用) ─────────────────────────

def search_via_hisannouncement(symbol: str, org_id: str, report_type: str, year: int = None) -> List[FinancialReport]:
    """
    使用巨潮个股历史公告 API
    URL: /new/hisAnnouncement/query
    """
    type_info = REPORT_TYPES[report_type]
    reports = []

    if symbol.startswith(("0", "3", "2")):
        column = "szse"
        category_map = {
            'annual': 'category_ndbg_szsh',
            'semi':   'category_bndbg_szsh',
            'q1':     'category_yjdbg_szsh',
            'q3':     'category_sjdbg_szsh',
        }
    else:
        column = "sse"
        category_map = {
            'annual': 'category_ndbg_sh',
            'semi':   'category_bndbg_sh',
            'q1':     'category_yjdbg_sh',
            'q3':     'category_sjdbg_sh',
        }
    category = category_map.get(report_type, 'category_ndbg_szsh')

    url = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
    params = {
        "pageNum": "1",
        "pageSize": "30",
        "tabName": "fulltext",
        "column": column,
        "category": category,
        "stock": f"{symbol},{org_id}",
        "isHLtitle": "true",
        "sortName": "time",
        "sortType": "desc",
    }
    if year:
        params["seDate"] = f"{year}-01-01~{year}-12-31"

    data = urllib.parse.urlencode(params).encode('utf-8')
    headers = {
        **BASE_HEADERS,
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://www.cninfo.com.cn",
        "Referer": f"https://www.cninfo.com.cn/new/disclosure/stock?stockCode={symbol}&orgId={org_id}",
    }

    try:
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read().decode('utf-8'))

        for item in (result.get('announcements') or []):
            title = item.get('announcementTitle', '')
            if not any(kw in title for kw in type_info['title_must']):
                continue
            if any(ex in title for ex in type_info['title_exclude']):
                continue

            year_match = re.search(r'20\d{2}', title)
            report_year = int(year_match.group()) if year_match else 0
            if year and report_year != year:
                continue

            adjunct_url = item.get('adjunctUrl', '')
            if adjunct_url:
                pdf_url = f"http://static.cninfo.com.cn/{adjunct_url}"
            else:
                t = str(item.get('announcementTime', ''))[:10]
                aid = item.get('announcementId', '')
                if t and aid:
                    pdf_url = f"http://static.cninfo.com.cn/finalpage/{t}/{aid}.PDF"
                else:
                    continue

            # 处理时间戳（毫秒转日期）
            raw_time = item.get('announcementTime', 0)
            if raw_time:
                # 毫秒时间戳转日期
                ts = raw_time / 1000 if raw_time > 1000000000000 else raw_time
                announce_date = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
            else:
                announce_date = ''

            reports.append(FinancialReport(
                title=title,
                report_type=report_type,
                year=report_year,
                announce_date=announce_date,
                pdf_url=pdf_url,
                source="巨潮个股公告",
                org_id=item.get('orgId', org_id),
                announcement_id=str(item.get('announcementId', '')),
            ))
    except Exception as e:
        print(f"  [个股公告] 失败: {e}", file=sys.stderr)

    return reports


# ───────────────────────── 综合查询 ─────────────────────────

def search_reports(symbol: str, stock_name: str, org_id: str,
                   report_type: str, year: int = None) -> List[FinancialReport]:
    """多路径查询，自动合并去重"""
    print(f"  路径1: 全文搜索API...")
    reports = search_via_fulltext(stock_name, symbol, report_type, year)

    if not reports and org_id:
        print(f"  路径2: 个股公告API...")
        reports = search_via_hisannouncement(symbol, org_id, report_type, year)

    # 去重（按 announcement_id 或 pdf_url）
    seen = set()
    unique = []
    for r in reports:
        key = r.announcement_id or r.pdf_url
        if key not in seen:
            seen.add(key)
            unique.append(r)

    return sorted(unique, key=lambda x: (x.year, x.announce_date), reverse=True)


def search_all_report_types(symbol: str, stock_name: str, org_id: str,
                            year: int = None) -> List[FinancialReport]:
    all_reports = []
    for rt in ['annual', 'semi', 'q1', 'q3']:
        rpts = search_reports(symbol, stock_name, org_id, rt, year)
        all_reports.extend(rpts)
    order = {'annual': 0, 'semi': 1, 'q1': 2, 'q3': 3}
    return sorted(all_reports, key=lambda x: (order.get(x.report_type, 9), -x.year))


# ───────────────────────── 下载 PDF ─────────────────────────

def download_pdf(url: str, output_path: str, verbose: bool = True) -> Tuple[bool, str]:
    headers = {
        **BASE_HEADERS,
        "Accept": "application/pdf,*/*",
        "Referer": "https://www.cninfo.com.cn/",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=120) as resp:
            content = resp.read()

        if len(content) < 1024:
            return False, f"文件太小({len(content)} 字节)，可能非有效PDF"
        if not content[:4] == b'%PDF' and not content[:4] == b'\xef\xbb\xbf%':
            # 某些PDF没有标准magic bytes也可以尝试保存
            if len(content) < 10240:
                return False, "内容不像PDF文件"

        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'wb') as f:
            f.write(content)
        return True, ""

    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return False, f"网络错误: {e.reason}"
    except Exception as e:
        return False, str(e)


# ───────────────────────── 主程序 ─────────────────────────

def print_reports_table(reports: List[FinancialReport]):
    print(f"\n{'#':<4} {'年份':<6} {'公告日期':<12} {'来源':<10} {'标题'}")
    print("-" * 80)
    for i, r in enumerate(reports, 1):
        print(f"{i:<4} {r.year:<6} {r.announce_date:<12} {r.source:<10} {r.title}")
    print()


def show_manual_links(symbol: str, stock_name: str, org_id: str, report_type: str):
    """显示手动下载链接"""
    type_name = REPORT_TYPES.get(report_type, {}).get('name', report_type)
    kw = urllib.parse.quote(f"{stock_name} {type_name}")
    print(f"\n{'─'*60}")
    print("手动下载渠道:")
    print(f"\n1. 巨潮全文搜索（推荐）:")
    print(f"   https://www.cninfo.com.cn/new/fulltextSearch"
          f"?notautosubmit=&keyWord={kw}&searchType=0")
    if org_id:
        print(f"\n2. 巨潮个股公告页:")
        print(f"   https://www.cninfo.com.cn/new/disclosure/stock"
              f"?stockCode={symbol}&orgId={org_id}")
    print(f"\n3. 东方财富公告中心:")
    print(f"   https://data.eastmoney.com/notices/stock/{symbol}/ANNUAL.html")
    print(f"{'─'*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description='上市公司财报PDF下载工具 v2.0',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('symbol', nargs='?', help='股票代码(6位)')
    parser.add_argument('--type', '-t',
                        choices=['annual', 'semi', 'q1', 'q3', 'all'],
                        default='annual', help='报告类型')
    parser.add_argument('--year', '-y', type=int, help='指定年份')
    parser.add_argument('--output', '-o', default='./reports', help='保存目录')
    parser.add_argument('--list', '-l', action='store_true', help='仅列出不下载')
    parser.add_argument('--all', '-a', action='store_true', help='下载所有匹配项')
    parser.add_argument('--url', '-u', help='直接下载指定PDF URL')
    parser.add_argument('--title', help='标题(配合--url)')
    args = parser.parse_args()

    # ── 直接URL下载模式 ──
    if args.url:
        symbol = (args.symbol or '000000').zfill(6)
        stock_name = symbol
        if args.symbol:
            print("查询股票信息...", end=' ', flush=True)
            stock_name, _ = get_stock_info(symbol)
            print(stock_name)

        title = args.title or f"报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        safe_title = re.sub(r'[\\/*?:"<>|]', '_', title)
        out_dir = os.path.join(args.output, f"{stock_name}_{symbol}")
        filepath = os.path.join(out_dir, f"{safe_title}.pdf")

        print(f"\n下载: {args.url}")
        print(f"保存: {filepath}")
        ok, err = download_pdf(args.url, filepath)
        if ok:
            mb = os.path.getsize(filepath) / 1024 / 1024
            print(f"✅ 成功 ({mb:.2f} MB): {filepath}")
        else:
            print(f"❌ 失败: {err}")
        return

    if not args.symbol:
        parser.print_help()
        sys.exit(1)

    symbol = args.symbol.zfill(6)

    print(f"\n{'='*70}")
    print(f"查询股票信息: {symbol}")
    stock_name, org_id = get_stock_info(symbol)
    print(f"股票: {stock_name}({symbol})  orgId: {org_id or '未获取'}")
    print(f"{'='*70}\n")

    # ── 查询报告 ──
    if args.type == 'all':
        print("查询所有类型报告...\n")
        reports = search_all_report_types(
            symbol, stock_name, org_id, args.year)
    else:
        type_name = REPORT_TYPES[args.type]['name']
        year_str = f" ({args.year}年)" if args.year else ""
        print(f"查询{type_name}{year_str}...\n")
        reports = search_reports(
            symbol, stock_name, org_id, args.type, args.year)

    if not reports:
        print(f"\n❌ 未找到匹配报告")
        show_manual_links(symbol, stock_name, org_id,
                          args.type if args.type != 'all' else 'annual')
        sys.exit(0)

    print(f"\n✅ 找到 {len(reports)} 份报告:")
    print_reports_table(reports)

    # ── 仅列表 ──
    if args.list:
        return

    # ── 下载 ──
    to_download = reports if args.all else [reports[0]]
    out_dir = os.path.join(args.output, f"{stock_name}_{symbol}")
    os.makedirs(out_dir, exist_ok=True)

    print(f"下载 {len(to_download)} 份报告 → {out_dir}\n")
    ok_count = 0

    for report in to_download:
        type_name = REPORT_TYPES.get(report.report_type, {}).get(
            'name', report.report_type)
        year_str = f"{report.year}年" if report.year else ""
        filename = f"{stock_name}_{symbol}_{year_str}{type_name}.pdf"
        filename = re.sub(r'[\\/*?:"<>|]', '_', filename)
        filepath = os.path.join(out_dir, filename)

        print(f"▶ {report.title}")
        print(f"  URL : {report.pdf_url}")

        ok, err = download_pdf(report.pdf_url, filepath)
        if ok:
            mb = os.path.getsize(filepath) / 1024 / 1024
            print(f"  ✅ 已保存 ({mb:.2f} MB): {filepath}")
            ok_count += 1
        else:
            print(f"  ❌ 失败: {err}")
            if report.announcement_id and report.org_id:
                detail_url = (
                    f"https://www.cninfo.com.cn/new/disclosure/detail"
                    f"?orgId={report.org_id}&announcementId={report.announcement_id}"
                )
                print(f"  手动: {detail_url}")
        print()

    print(f"{'='*70}")
    print(
        f"完成: {ok_count}/{len(to_download)} 成功  |  目录: {os.path.abspath(out_dir)}")
    print(f"{'='*70}")


if __name__ == '__main__':
    main()
