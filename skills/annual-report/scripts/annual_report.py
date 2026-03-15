#!/usr/bin/env python3
"""
上市公司年报分析工具
支持年报下载、PDF解析、财务分析、文本分析、异常检测
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any
import warnings
warnings.filterwarnings('ignore')

# 尝试导入依赖
try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


# 配置
DEFAULT_STORAGE_PATH = Path.home() / ".openclaw" / "workspace" / "annual-reports"
CNINFO_BASE_URL = "https://www.cninfo.com.cn"
CNINFO_SEARCH_URL = "https://www.cninfo.com.cn/new/fulltextSearch"
CNINFO_DOWNLOAD_URL = "https://static.cninfo.com.cn"
CNINFO_API_URL = "https://www.cninfo.com.cn/new/hisAnnouncement/query"


def get_storage_path(symbol: str) -> Path:
    """获取存储路径"""
    path = DEFAULT_STORAGE_PATH / symbol
    path.mkdir(parents=True, exist_ok=True)
    return path


def http_get(url: str, headers: dict = None, timeout: int = 30) -> str:
    """HTTP GET 请求"""
    default_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    if headers:
        default_headers.update(headers)
    
    if not HAS_REQUESTS:
        import urllib.request
        req = urllib.request.Request(url, headers=default_headers)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode('utf-8', errors='ignore')
    
    resp = requests.get(url, headers=default_headers, timeout=timeout)
    resp.encoding = 'utf-8'
    return resp.text


def http_download(url: str, save_path: str, headers: dict = None) -> bool:
    """下载文件"""
    default_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    if headers:
        default_headers.update(headers)
    
    try:
        if not HAS_REQUESTS:
            import urllib.request
            req = urllib.request.Request(url, headers=default_headers)
            with urllib.request.urlopen(req, timeout=60) as response:
                with open(save_path, 'wb') as f:
                    f.write(response.read())
            return True
        
        resp = requests.get(url, headers=default_headers, timeout=60, stream=True)
        with open(save_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        print(f"下载失败: {e}")
        return False


# ============================================================
# 年报下载模块
# ============================================================

def get_stock_name(symbol: str) -> str:
    """根据股票代码获取股票名称（简单映射）"""
    stock_names = {
        "600519": "贵州茅台",
        "000001": "平安银行",
        "000002": "万科A",
        "600036": "招商银行",
        "601318": "中国平安",
        "600276": "恒瑞医药",
        "000858": "五粮液",
        "002916": "深南电路",
        "002475": "立讯精密",
        "300750": "宁德时代",
        "601012": "隆基绿能",
        "600900": "长江电力",
        "002415": "海康威视",
        "300059": "东方财富",
        "601888": "中国中免",
        "000651": "格力电器",
        "002594": "比亚迪",
        "601398": "工商银行",
        "601288": "农业银行",
        "600030": "中信证券",
        "601166": "兴业银行",
        "600000": "浦发银行",
        "601328": "交通银行",
    }
    return stock_names.get(symbol, symbol)


def search_annual_report_cninfo(symbol: str, year: int) -> Optional[Dict]:
    """从巨潮资讯搜索年报"""
    if not HAS_REQUESTS:
        return {"error": "需要安装 requests"}
    
    try:
        # 使用 Session 保持 cookie
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        })
        
        # 关键步骤：先访问首页获取 cookie
        session.get("https://www.cninfo.com.cn/", timeout=15)
        
        # 根据股票代码判断交易所
        if symbol.startswith("6"):
            column = "sse"  # 上交所
        else:
            column = "szse"  # 深交所
        
        # 获取股票名称构造搜索关键词（不要带具体年份）
        stock_name = get_stock_name(symbol)
        search_keyword = f"{stock_name} 年度报告"
        
        # 设置搜索时间范围（年报通常在次年4月发布）
        se_date = f"{year+1}-01-01~{year+1}-06-30"
        
        headers = {
            "Accept": "application/json",
            "Referer": "https://www.cninfo.com.cn/new/fulltextSearch",
            "X-Requested-With": "XMLHttpRequest",
        }
        
        api_url = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
        
        # 关键：使用 searchkey 参数
        data = {
            "pageNum": "1",
            "pageSize": "30",
            "tabName": "fulltext",
            "column": column,
            "searchkey": search_keyword,
            "seDate": se_date,
        }
        
        resp = session.post(api_url, data=data, headers=headers, timeout=20)
        result = resp.json()
        
        if result.get("announcements"):
            for item in result["announcements"]:
                title = item.get("announcementTitle", "")
                # 匹配年度报告，排除摘要、英文版等，并匹配年份
                if (f"{year}年年度报告" in title or f"{year} 年度报告" in title) and "摘要" not in title and "英文" not in title:
                    adjunct_url = item.get("adjunctUrl", "")
                    announcement_id = item.get("announcementId", "")
                    org_id = item.get("orgId", "")
                    announcement_time = item.get("announcementTime", "")
                    
                    # 构造下载链接
                    if adjunct_url:
                        pdf_url = f"https://static.cninfo.com.cn/{adjunct_url}"
                    else:
                        continue
                    
                    return {
                        "title": title,
                        "url": pdf_url,
                        "announcement_id": announcement_id,
                        "org_id": org_id,
                        "publish_date": announcement_time,
                        "source": "巨潮资讯",
                        "session": session,  # 返回 session 用于下载
                    }
        
        return None
    except Exception as e:
        return {"error": str(e)}


def get_annual_report_url_sse(symbol: str, year: int) -> Optional[Dict]:
    """从上交所获取年报链接"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.sse.com.cn/",
        }
        
        sse_url = "https://query.sse.com.cn/security/stock/queryCompanyBulletin.do"
        params = {
            "isPagination": "true",
            "productId": symbol,
            "securityType": "0101",
            "reportType": "ALL",
            "beginPage": "1",
            "singleOrderBy": "1",
            "keyWord": "年度报告",
        }
        
        resp = requests.get(sse_url, params=params, headers=headers, timeout=15)
        data = resp.json()
        
        if data.get("result"):
            for item in data["result"]:
                title = item.get("TITLE", "")
                url = item.get("URL", "")
                # 匹配年报年份
                if str(year) in title and "年度报告" in title and "摘要" not in title and "英文" not in title:
                    if url:
                        return {
                            "title": title,
                            "url": f"https://www.sse.com.cn{url}",
                            "publish_date": item.get("SSEDATE", ""),
                            "source": "上交所"
                        }
        return None
    except Exception as e:
        return {"error": str(e)}


def get_annual_report_url_eastmoney(symbol: str, year: int) -> Optional[Dict]:
    """从东方财富获取年报链接"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "*/*",
            "Referer": "https://data.eastmoney.com/",
        }
        
        # 东方财富公告查询接口 - 需要添加时间筛选
        year_start = f"{year}-01-01"
        year_end = f"{year + 1}-06-30"
        url = f"https://np-anotice-stock.eastmoney.com/api/security/ann?cb=jQuery&sr=-1&page_size=100&page_index=1&ann_type=SHA,SZA&client_source=web&stock_list={symbol}&f_node=0&s_node=0&begin_date={year_start}&end_date={year_end}"
        
        resp = requests.get(url, headers=headers, timeout=15)
        text = resp.text
        
        # 解析 JSONP 响应
        match = re.search(r'jQuery\((.*)\)', text)
        if match:
            data = json.loads(match.group(1))
            
            if data.get("data") and data["data"].get("list"):
                for item in data["data"]["list"]:
                    title = item.get("title", "")
                    # 年报通常在次年 4 月发布，所以检查年份
                    if str(year) in title and "年度报告" in title and "摘要" not in title:
                        ann_id = item.get("art_code", "")
                        if ann_id:
                            return {
                                "title": title,
                                "art_code": ann_id,
                                "url": f"https://pdf.dfcfw.com/pdf/H3_{ann_id}_1.pdf",
                                "notice_date": item.get("notice_date", ""),
                                "source": "东方财富"
                            }
        
        return None
    except Exception as e:
        return {"error": str(e)}


def download_annual_report(symbol: str, year: int) -> Dict:
    """下载年报 PDF"""
    storage_path = get_storage_path(symbol)
    pdf_path = storage_path / f"{year}.pdf"
    
    # 如果已存在，直接返回
    if pdf_path.exists():
        file_size = pdf_path.stat().st_size
        if file_size > 10000:  # 文件大于 10KB 才认为有效
            return {
                "status": "exists",
                "message": f"年报已存在: {pdf_path}",
                "path": str(pdf_path),
                "size": file_size
            }
    
    # 优先从巨潮资讯获取（成功率最高）
    report_info = search_annual_report_cninfo(symbol, year)
    if report_info and "error" not in report_info and report_info.get("url"):
        session = report_info.get("session")
        try:
            if session:
                # 使用同一个 session 下载
                resp = session.get(report_info["url"], timeout=60, stream=True)
                content = resp.content
                if content[:4] == b'%PDF':
                    with open(pdf_path, 'wb') as f:
                        f.write(content)
                    file_size = pdf_path.stat().st_size
                    return {
                        "status": "success",
                        "message": f"年报下载成功",
                        "path": str(pdf_path),
                        "source": "巨潮资讯",
                        "title": report_info.get("title", ""),
                        "size": file_size
                    }
            else:
                # 回退到普通下载
                if http_download(report_info["url"], str(pdf_path)):
                    file_size = pdf_path.stat().st_size if pdf_path.exists() else 0
                    if file_size > 10000:
                        return {
                            "status": "success",
                            "message": f"年报下载成功",
                            "path": str(pdf_path),
                            "source": "巨潮资讯",
                            "title": report_info.get("title", ""),
                            "size": file_size
                        }
        except Exception as e:
            pdf_path.unlink(missing_ok=True)
    
    # 尝试从上交所获取
    if symbol.startswith("6"):
        report_info = get_annual_report_url_sse(symbol, year)
        if report_info and "error" not in report_info and report_info.get("url"):
            if http_download(report_info["url"], str(pdf_path)):
                file_size = pdf_path.stat().st_size if pdf_path.exists() else 0
                if file_size > 10000:
                    return {
                        "status": "success",
                        "message": f"年报下载成功",
                        "path": str(pdf_path),
                        "source": report_info.get("source", "上交所"),
                        "title": report_info.get("title", ""),
                        "size": file_size
                    }
                else:
                    pdf_path.unlink(missing_ok=True)
    
    # 尝试东方财富
    report_info = get_annual_report_url_eastmoney(symbol, year)
    if report_info and "error" not in report_info and report_info.get("url"):
        if http_download(report_info["url"], str(pdf_path)):
            file_size = pdf_path.stat().st_size if pdf_path.exists() else 0
            if file_size > 10000:
                return {
                    "status": "success",
                    "message": f"年报下载成功",
                    "path": str(pdf_path),
                    "source": report_info.get("source", "东方财富"),
                    "title": report_info.get("title", ""),
                    "size": file_size
                }
            else:
                pdf_path.unlink(missing_ok=True)
    
    return {
        "status": "failed",
        "message": "无法获取年报下载链接，请手动下载",
        "manual_hints": [
            f"巨潮资讯: http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/fulltextSearch",
            f"上海证券交易所: http://www.sse.com.cn/assortment/stocks/list/info/",
            f"深圳证券交易所: http://www.szse.cn/disclosure/listed/fixed/index.html",
        ],
        "suggested_path": str(pdf_path)
    }


def import_local_pdf(local_path: str, symbol: str, year: int) -> Dict:
    """导入本地 PDF 文件到年报目录"""
    import shutil
    
    local_file = Path(local_path)
    if not local_file.exists():
        return {"error": f"本地文件不存在: {local_path}"}
    
    if not local_file.suffix.lower() == '.pdf':
        return {"error": "文件必须是 PDF 格式"}
    
    storage_path = get_storage_path(symbol)
    pdf_path = storage_path / f"{year}.pdf"
    
    try:
        shutil.copy2(local_file, pdf_path)
        file_size = pdf_path.stat().st_size
        return {
            "status": "success",
            "message": f"PDF 已导入到年报目录",
            "source": str(local_file),
            "path": str(pdf_path),
            "size": file_size
        }
    except Exception as e:
        return {"error": str(e)}


def list_local_reports(symbol: str = None) -> Dict:
    """列出本地已有的年报"""
    if not DEFAULT_STORAGE_PATH.exists():
        return {"status": "empty", "message": "暂无本地年报"}
    
    reports = []
    
    if symbol:
        symbol_path = DEFAULT_STORAGE_PATH / symbol
        if symbol_path.exists():
            for pdf_file in symbol_path.glob("*.pdf"):
                reports.append({
                    "symbol": symbol,
                    "year": pdf_file.stem,
                    "path": str(pdf_file),
                    "size": pdf_file.stat().st_size
                })
    else:
        for symbol_dir in DEFAULT_STORAGE_PATH.iterdir():
            if symbol_dir.is_dir():
                for pdf_file in symbol_dir.glob("*.pdf"):
                    reports.append({
                        "symbol": symbol_dir.name,
                        "year": pdf_file.stem,
                        "path": str(pdf_file),
                        "size": pdf_file.stat().st_size
                    })
    
    if not reports:
        return {"status": "empty", "message": "暂无本地年报"}
    
    return {
        "status": "success",
        "total": len(reports),
        "reports": sorted(reports, key=lambda x: (x["symbol"], x["year"]))
    }


# ============================================================
# PDF 解析模块
# ============================================================

def parse_pdf_text(pdf_path: str) -> Dict:
    """解析 PDF 文本内容"""
    if not HAS_PDFPLUMBER:
        return {"error": "需要安装 pdfplumber: pip install pdfplumber"}
    
    if not os.path.exists(pdf_path):
        return {"error": f"PDF 文件不存在: {pdf_path}"}
    
    try:
        text_by_page = []
        all_text = []
        
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                text_by_page.append({
                    "page": i + 1,
                    "text": text
                })
                all_text.append(text)
        
        return {
            "status": "success",
            "total_pages": total_pages,
            "text_by_page": text_by_page,
            "full_text": "\n\n".join(all_text)
        }
    except Exception as e:
        return {"error": str(e)}


def extract_tables_from_pdf(pdf_path: str) -> Dict:
    """从 PDF 提取表格"""
    if not HAS_PDFPLUMBER:
        return {"error": "需要安装 pdfplumber"}
    
    if not os.path.exists(pdf_path):
        return {"error": f"PDF 文件不存在: {pdf_path}"}
    
    try:
        all_tables = []
        
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                tables = page.extract_tables()
                for j, table in enumerate(tables):
                    all_tables.append({
                        "page": i + 1,
                        "table_index": j,
                        "data": table
                    })
        
        return {
            "status": "success",
            "total_tables": len(all_tables),
            "tables": all_tables
        }
    except Exception as e:
        return {"error": str(e)}


# ============================================================
# 财务报表解析模块
# ============================================================

def find_financial_statement_tables(tables: List[Dict], keywords: List[str]) -> List[Dict]:
    """查找包含特定关键词的表格"""
    matched = []
    for table in tables:
        if not table.get("data"):
            continue
        # 检查表格标题行
        first_rows = table["data"][:3] if len(table["data"]) >= 3 else table["data"]
        text = " ".join([" ".join([str(cell) for cell in row if cell]) for row in first_rows])
        
        if any(kw in text for kw in keywords):
            matched.append(table)
    
    return matched


def parse_income_statement(tables: List[Dict], text: str) -> Dict:
    """解析利润表"""
    income_keywords = ["营业收入", "营业成本", "利润总额", "净利润", "利润表"]
    matched_tables = find_financial_statement_tables(tables, income_keywords)
    
    result = {
        "status": "success",
        "data": {},
        "raw_tables": []
    }
    
    # 关键指标提取
    patterns = {
        "营业收入": r"营业收入[^\d]*(\d+[,.]?\d*[,.]?\d*)",
        "营业成本": r"营业成本[^\d]*(\d+[,.]?\d*[,.]?\d*)",
        "毛利": r"毛利[^\d]*(\d+[,.]?\d*[,.]?\d*)",
        "营业利润": r"营业利润[^\d]*(\d+[,.]?\d*[,.]?\d*)",
        "利润总额": r"利润总额[^\d]*(\d+[,.]?\d*[,.]?\d*)",
        "净利润": r"净利润[^\d]*(\d+[,.]?\d*[,.]?\d*)",
        "基本每股收益": r"基本每股收益[^\d]*([\d.]+)",
        "稀释每股收益": r"稀释每股收益[^\d]*([\d.]+)",
    }
    
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            value = match.group(1).replace(",", "").replace("，", "")
            try:
                result["data"][key] = float(value)
            except:
                result["data"][key] = value
    
    # 保存原始表格
    for t in matched_tables[:3]:
        result["raw_tables"].append({
            "page": t["page"],
            "data": t["data"][:10] if len(t["data"]) > 10 else t["data"]
        })
    
    return result


def parse_balance_sheet(tables: List[Dict], text: str) -> Dict:
    """解析资产负债表"""
    balance_keywords = ["资产总计", "负债合计", "所有者权益", "资产负债表"]
    matched_tables = find_financial_statement_tables(tables, balance_keywords)
    
    result = {
        "status": "success",
        "data": {},
        "raw_tables": []
    }
    
    patterns = {
        "流动资产": r"流动资产合计[^\d]*(\d+[,.]?\d*[,.]?\d*)",
        "非流动资产": r"非流动资产合计[^\d]*(\d+[,.]?\d*[,.]?\d*)",
        "资产总计": r"资产总计[^\d]*(\d+[,.]?\d*[,.]?\d*)",
        "流动负债": r"流动负债合计[^\d]*(\d+[,.]?\d*[,.]?\d*)",
        "非流动负债": r"非流动负债合计[^\d]*(\d+[,.]?\d*[,.]?\d*)",
        "负债合计": r"负债合计[^\d]*(\d+[,.]?\d*[,.]?\d*)",
        "股本": r"股本[^\d]*(\d+[,.]?\d*[,.]?\d*)",
        "资本公积": r"资本公积[^\d]*(\d+[,.]?\d*[,.]?\d*)",
        "盈余公积": r"盈余公积[^\d]*(\d+[,.]?\d*[,.]?\d*)",
        "未分配利润": r"未分配利润[^\d]*(\d+[,.]?\d*[,.]?\d*)",
        "所有者权益合计": r"所有者权益[合]?计[^\d]*(\d+[,.]?\d*[,.]?\d*)",
    }
    
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            value = match.group(1).replace(",", "").replace("，", "")
            try:
                result["data"][key] = float(value)
            except:
                result["data"][key] = value
    
    for t in matched_tables[:3]:
        result["raw_tables"].append({
            "page": t["page"],
            "data": t["data"][:10] if len(t["data"]) > 10 else t["data"]
        })
    
    return result


def parse_cash_flow_statement(tables: List[Dict], text: str) -> Dict:
    """解析现金流量表"""
    cash_keywords = ["经营活动", "投资活动", "筹资活动", "现金流量表"]
    matched_tables = find_financial_statement_tables(tables, cash_keywords)
    
    result = {
        "status": "success",
        "data": {},
        "raw_tables": []
    }
    
    patterns = {
        "经营活动现金流入": r"经营活动[产生]*的现金流入小?计[^\d]*(\d+[,.]?\d*[,.]?\d*)",
        "经营活动现金流出": r"经营活动[产生]*的现金流出小?计[^\d]*(\d+[,.]?\d*[,.]?\d*)",
        "经营活动现金流量净额": r"经营活动[产生]*的现金流量净额[^\d]*(\-?\d+[,.]?\d*[,.]?\d*)",
        "投资活动现金流量净额": r"投资活动[产生]*的现金流量净额[^\d]*(\-?\d+[,.]?\d*[,.]?\d*)",
        "筹资活动现金流量净额": r"筹资活动[产生]*的现金流量净额[^\d]*(\-?\d+[,.]?\d*[,.]?\d*)",
        "现金及现金等价物净增加额": r"现金及现金等价物净增加额[^\d]*(\-?\d+[,.]?\d*[,.]?\d*)",
    }
    
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            value = match.group(1).replace(",", "").replace("，", "")
            try:
                result["data"][key] = float(value)
            except:
                result["data"][key] = value
    
    for t in matched_tables[:3]:
        result["raw_tables"].append({
            "page": t["page"],
            "data": t["data"][:10] if len(t["data"]) > 10 else t["data"]
        })
    
    return result


# ============================================================
# 财务指标计算模块
# ============================================================

def calculate_financial_indicators(
    income: Dict,
    balance: Dict,
    cash_flow: Dict,
    prev_year_data: Optional[Dict] = None
) -> Dict:
    """计算核心财务指标"""
    result = {
        "profitability": {},  # 盈利能力
        "solvency": {},       # 偿债能力
        "growth": {},         # 成长能力
        "operation": {},      # 运营能力
        "cash_quality": {},   # 现金流质量
    }
    
    income_data = income.get("data", {})
    balance_data = balance.get("data", {})
    cash_data = cash_flow.get("data", {})
    
    # 盈利能力指标
    revenue = income_data.get("营业收入", 0)
    net_profit = income_data.get("净利润", 0)
    total_assets = balance_data.get("资产总计", 0)
    equity = balance_data.get("所有者权益合计", 0)
    
    if revenue > 0:
        result["profitability"]["净利率"] = round(net_profit / revenue, 4) if net_profit else 0
        
        operating_cost = income_data.get("营业成本", 0)
        if operating_cost:
            gross_profit = revenue - operating_cost
            result["profitability"]["毛利率"] = round(gross_profit / revenue, 4)
    
    if equity > 0:
        result["profitability"]["ROE"] = round(net_profit / equity, 4) if net_profit else 0
    
    if total_assets > 0:
        result["profitability"]["ROA"] = round(net_profit / total_assets, 4) if net_profit else 0
    
    # 偿债能力指标
    current_assets = balance_data.get("流动资产", 0)
    current_liabilities = balance_data.get("流动负债", 0)
    total_liabilities = balance_data.get("负债合计", 0)
    inventory = balance_data.get("存货", 0)  # 如果有
    
    if total_assets > 0:
        result["solvency"]["资产负债率"] = round(total_liabilities / total_assets, 4)
    
    if current_liabilities > 0:
        result["solvency"]["流动比率"] = round(current_assets / current_liabilities, 2)
        quick_assets = current_assets - inventory
        result["solvency"]["速动比率"] = round(quick_assets / current_liabilities, 2) if quick_assets else 0
    
    # 现金流质量
    operating_cf = cash_data.get("经营活动现金流量净额", 0)
    
    if net_profit > 0:
        result["cash_quality"]["经营现金流/净利润"] = round(operating_cf / net_profit, 2) if operating_cf else 0
    
    if revenue > 0:
        result["cash_quality"]["销售收现比"] = round(operating_cf / revenue, 4) if operating_cf else 0
    
    # 成长能力（需要上年数据）
    if prev_year_data:
        prev_income = prev_year_data.get("income", {}).get("data", {})
        prev_revenue = prev_income.get("营业收入", 0)
        prev_net_profit = prev_income.get("净利润", 0)
        
        if prev_revenue > 0:
            result["growth"]["营收增长率"] = round((revenue - prev_revenue) / prev_revenue, 4)
        
        if prev_net_profit > 0:
            result["growth"]["净利润增长率"] = round((net_profit - prev_net_profit) / prev_net_profit, 4)
    
    return result


# ============================================================
# 文本分析模块
# ============================================================

def extract_mda_section(text: str) -> Dict:
    """提取管理层讨论与分析章节"""
    result = {
        "status": "success",
        "content": "",
        "highlights": []
    }
    
    # 常见章节标题
    mda_patterns = [
        r"管理层讨论与分析(.*?)(?=重要事项|股份变动|$)",
        r"董事会报告(.*?)(?=重要事项|股份变动|$)",
        r"经营情况讨论与分析(.*?)(?=重要事项|$)",
    ]
    
    for pattern in mda_patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            result["content"] = match.group(1)[:5000]  # 限制长度
            break
    
    # 提取关键信息
    highlight_patterns = {
        "主营业务": r"主营业务[：:](.*?)(?=\n|$)",
        "核心竞争力": r"核心竞争力[：:](.*?)(?=\n|$)",
        "未来展望": r"未来[发展]*展望[：:](.*?)(?=\n|$)",
        "风险因素": r"风险[因素]*(.*?)(?=\n\n|$)",
    }
    
    for key, pattern in highlight_patterns.items():
        match = re.search(pattern, result["content"], re.DOTALL)
        if match:
            result["highlights"].append({
                "topic": key,
                "content": match.group(1)[:500]
            })
    
    return result


def detect_audit_opinion(text: str) -> Dict:
    """识别审计意见类型"""
    result = {
        "status": "success",
        "opinion_type": "未知",
        "auditor": "",
        "details": ""
    }
    
    # 审计意见类型
    opinion_patterns = [
        (r"标准无保留意见", "标准无保留意见"),
        (r"无保留意见", "无保留意见"),
        (r"带强调事项段的无保留意见", "带强调事项段的无保留意见"),
        (r"保留意见", "保留意见"),
        (r"否定意见", "否定意见"),
        (r"无法表示意见", "无法表示意见"),
    ]
    
    for pattern, opinion_type in opinion_patterns:
        if re.search(pattern, text):
            result["opinion_type"] = opinion_type
            break
    
    # 提取审计机构
    auditor_match = re.search(r"审计机构[：:]?\s*(.+?)(?:\n|$)", text)
    if auditor_match:
        result["auditor"] = auditor_match.group(1).strip()
    
    return result


def extract_risk_disclosures(text: str) -> Dict:
    """提取风险披露"""
    result = {
        "status": "success",
        "risks": [],
        "litigation": [],
        "related_transactions": []
    }
    
    # 诉讼风险
    litigation_patterns = [
        r"诉讼[：:](.*?)(?=\n\n|$)",
        r"仲裁[：:](.*?)(?=\n\n|$)",
        r"重大诉讼[：:](.*?)(?=\n\n|$)",
    ]
    
    for pattern in litigation_patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        for m in matches:
            if len(m.strip()) > 20:
                result["litigation"].append(m.strip()[:500])
    
    # 关联交易
    related_patterns = [
        r"关联交易[：:](.*?)(?=\n\n|$)",
        r"关联方交易[：:](.*?)(?=\n\n|$)",
    ]
    
    for pattern in related_patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        for m in matches:
            if len(m.strip()) > 20:
                result["related_transactions"].append(m.strip()[:500])
    
    # 一般风险
    risk_section = re.search(r"可能面对的风险[：:](.*?)(?=\n\n|$)", text, re.DOTALL)
    if risk_section:
        result["risks"].append(risk_section.group(1).strip()[:1000])
    
    return result


def extract_business_segments(text: str) -> Dict:
    """解析主营业务分部收入结构"""
    result = {
        "status": "success",
        "segments": []
    }
    
    # 查找分部收入表格
    patterns = [
        r"主营业务分[行业产品]*情况",
        r"分[行业产品]收入",
        r"主营业务收入构成",
    ]
    
    segment_texts = []
    for pattern in patterns:
        matches = re.findall(pattern + r"(.*?)(?=\n\n|其他业务|$)", text, re.DOTALL)
        segment_texts.extend(matches)
    
    # 提取关键数据
    for seg_text in segment_texts[:3]:
        lines = seg_text.split("\n")
        for line in lines:
            if any(kw in line for kw in ["收入", "占比", "%"]):
                result["segments"].append(line.strip())
    
    return result


# ============================================================
# 异常检测模块
# ============================================================

def detect_financial_anomalies(
    indicators: Dict,
    prev_years_data: List[Dict],
    industry_avg: Optional[Dict] = None
) -> Dict:
    """检测财务异常"""
    result = {
        "status": "success",
        "anomalies": [],
        "warnings": []
    }
    
    profitability = indicators.get("profitability", {})
    solvency = indicators.get("solvency", {})
    cash_quality = indicators.get("cash_quality", {})
    
    # 1. 现金流预警：净利润高但经营现金流为负
    if profitability.get("净利率", 0) > 0.1:
        if cash_quality.get("经营现金流/净利润", 1) < 0:
            result["anomalies"].append({
                "type": "现金流预警",
                "severity": "high",
                "description": "净利润为正但经营现金流为负",
                "detail": f"净利率 {profitability.get('净利率', 0):.2%}，但经营现金流/净利润为 {cash_quality.get('经营现金流/净利润', 0):.2f}"
            })
    
    # 2. 盈利能力异常
    roe = profitability.get("ROE", 0)
    if roe > 0.5:
        result["warnings"].append({
            "type": "盈利能力异常高",
            "severity": "medium",
            "description": f"ROE 超过 50%，需验证可持续性",
            "value": f"ROE: {roe:.2%}"
        })
    
    # 3. 偿债风险
    debt_ratio = solvency.get("资产负债率", 0)
    if debt_ratio > 0.8:
        result["anomalies"].append({
            "type": "高负债风险",
            "severity": "high",
            "description": "资产负债率超过 80%",
            "value": f"资产负债率: {debt_ratio:.2%}"
        })
    
    current_ratio = solvency.get("流动比率", 0)
    if current_ratio < 1:
        result["anomalies"].append({
            "type": "流动性风险",
            "severity": "high",
            "description": "流动比率低于 1，短期偿债压力大",
            "value": f"流动比率: {current_ratio:.2f}"
        })
    
    # 4. 多年趋势分析
    if len(prev_years_data) >= 2:
        # 检查应收账款周转率下降
        # 检查存货周转率下降
        # 检查毛利率大幅波动
        pass
    
    # 5. 财务造假预警信号
    fraud_signals = []
    
    # 信号1: 净利润与经营现金流长期背离
    if cash_quality.get("经营现金流/净利润", 1) < 0.5:
        fraud_signals.append("净利润与经营现金流严重背离")
    
    # 信号2: 毛利率显著高于行业
    if industry_avg:
        gross_margin = profitability.get("毛利率", 0)
        industry_gm = industry_avg.get("毛利率", 0)
        if gross_margin > industry_gm * 1.5:
            fraud_signals.append(f"毛利率 {gross_margin:.2%} 显著高于行业平均 {industry_gm:.2%}")
    
    if fraud_signals:
        result["anomalies"].append({
            "type": "财务造假风险信号",
            "severity": "medium",
            "description": "存在潜在财务造假风险信号",
            "signals": fraud_signals
        })
    
    return result


# ============================================================
# 主功能函数
# ============================================================

def parse_annual_report(symbol: str, year: int) -> Dict:
    """解析年报"""
    storage_path = get_storage_path(symbol)
    pdf_path = storage_path / f"{year}.pdf"
    
    if not pdf_path.exists():
        return {"error": f"请先下载年报: python annual_report.py --action download --symbol {symbol} --year {year}"}
    
    # 解析 PDF
    text_result = parse_pdf_text(str(pdf_path))
    if "error" in text_result:
        return text_result
    
    tables_result = extract_tables_from_pdf(str(pdf_path))
    
    text = text_result.get("full_text", "")
    tables = tables_result.get("tables", [])
    
    # 解析三表
    income_statement = parse_income_statement(tables, text)
    balance_sheet = parse_balance_sheet(tables, text)
    cash_flow_statement = parse_cash_flow_statement(tables, text)
    
    result = {
        "status": "success",
        "symbol": symbol,
        "year": year,
        "total_pages": text_result.get("total_pages", 0),
        "income_statement": income_statement,
        "balance_sheet": balance_sheet,
        "cash_flow_statement": cash_flow_statement,
    }
    
    # 保存解析结果
    parsed_path = storage_path / f"{year}_parsed.json"
    with open(parsed_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    
    return result


def analyze_annual_report(symbol: str, year: int) -> Dict:
    """分析年报"""
    storage_path = get_storage_path(symbol)
    parsed_path = storage_path / f"{year}_parsed.json"
    
    if not parsed_path.exists():
        parse_result = parse_annual_report(symbol, year)
        if "error" in parse_result:
            return parse_result
    
    with open(parsed_path, 'r', encoding='utf-8') as f:
        parsed_data = json.load(f)
    
    # 计算财务指标
    indicators = calculate_financial_indicators(
        parsed_data.get("income_statement", {}),
        parsed_data.get("balance_sheet", {}),
        parsed_data.get("cash_flow_statement", {})
    )
    
    result = {
        "status": "success",
        "symbol": symbol,
        "year": year,
        "indicators": indicators,
    }
    
    # 保存分析结果
    analysis_path = storage_path / f"{year}_analysis.json"
    with open(analysis_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    return result


def text_analysis(symbol: str, year: int) -> Dict:
    """文本分析"""
    storage_path = get_storage_path(symbol)
    pdf_path = storage_path / f"{year}.pdf"
    
    if not pdf_path.exists():
        return {"error": f"请先下载年报"}
    
    text_result = parse_pdf_text(str(pdf_path))
    if "error" in text_result:
        return text_result
    
    text = text_result.get("full_text", "")
    
    result = {
        "status": "success",
        "symbol": symbol,
        "year": year,
        "mda_analysis": extract_mda_section(text),
        "audit_opinion": detect_audit_opinion(text),
        "risk_disclosures": extract_risk_disclosures(text),
        "business_segments": extract_business_segments(text),
    }
    
    # 保存文本分析结果
    text_analysis_path = storage_path / f"{year}_text_analysis.json"
    with open(text_analysis_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    
    return result


def full_report(symbol: str, year: int, output_format: str = "json") -> Dict:
    """生成完整分析报告"""
    # 下载年报
    download_result = download_annual_report(symbol, year)
    
    # 解析年报
    parse_result = parse_annual_report(symbol, year)
    if "error" in parse_result:
        return parse_result
    
    # 财务分析
    analysis_result = analyze_annual_report(symbol, year)
    
    # 文本分析
    text_result = text_analysis(symbol, year)
    
    # 异常检测
    anomaly_result = detect_financial_anomalies(
        analysis_result.get("indicators", {}),
        []
    )
    
    result = {
        "status": "success",
        "symbol": symbol,
        "year": year,
        "generated_at": datetime.now().isoformat(),
        "download": download_result,
        "financial_indicators": analysis_result.get("indicators", {}),
        "text_analysis": {
            "audit_opinion": text_result.get("audit_opinion", {}),
            "risks": text_result.get("risk_disclosures", {}).get("risks", []),
            "litigation": text_result.get("risk_disclosures", {}).get("litigation", []),
        },
        "anomaly_detection": anomaly_result,
    }
    
    if output_format == "markdown":
        return format_markdown_report(result)
    
    return result


def format_markdown_report(data: Dict) -> str:
    """格式化为 Markdown 报告"""
    md = f"""# {data.get('symbol', '')} {data.get('year', '')} 年报分析报告

生成时间: {data.get('generated_at', '')}

## 1. 财务指标分析

### 盈利能力
"""
    
    profitability = data.get("financial_indicators", {}).get("profitability", {})
    for key, value in profitability.items():
        if isinstance(value, float):
            md += f"- **{key}**: {value:.2%}\n"
        else:
            md += f"- **{key}**: {value}\n"
    
    md += "\n### 偿债能力\n"
    solvency = data.get("financial_indicators", {}).get("solvency", {})
    for key, value in solvency.items():
        if isinstance(value, float):
            md += f"- **{key}**: {value:.2f}\n"
        else:
            md += f"- **{key}**: {value}\n"
    
    md += "\n## 2. 审计意见\n"
    audit = data.get("text_analysis", {}).get("audit_opinion", {})
    md += f"- **意见类型**: {audit.get('opinion_type', '未知')}\n"
    md += f"- **审计机构**: {audit.get('auditor', '未知')}\n"
    
    md += "\n## 3. 风险提示\n"
    anomalies = data.get("anomaly_detection", {}).get("anomalies", [])
    if anomalies:
        for a in anomalies:
            md += f"- [{a.get('severity', '').upper()}] {a.get('description', '')}\n"
    else:
        md += "- 暂无明显风险信号\n"
    
    return md


def compare_years(symbol: str, years: List[int]) -> Dict:
    """多年对比分析"""
    results = {}
    
    for year in years:
        analysis = analyze_annual_report(symbol, year)
        if "error" not in analysis:
            results[year] = analysis
    
    if len(results) < 2:
        return {"error": "需要至少两年的数据才能进行对比"}
    
    # 计算趋势
    trends = {}
    years_sorted = sorted(results.keys())
    
    for i in range(1, len(years_sorted)):
        prev_year = years_sorted[i-1]
        curr_year = years_sorted[i]
        
        prev_ind = results[prev_year].get("indicators", {}).get("profitability", {})
        curr_ind = results[curr_year].get("indicators", {}).get("profitability", {})
        
        trends[f"{prev_year}-{curr_year}"] = {
            "ROE变化": curr_ind.get("ROE", 0) - prev_ind.get("ROE", 0),
            "毛利率变化": curr_ind.get("毛利率", 0) - prev_ind.get("毛利率", 0),
        }
    
    return {
        "status": "success",
        "symbol": symbol,
        "years": years,
        "annual_data": results,
        "trends": trends
    }


def main():
    parser = argparse.ArgumentParser(description="上市公司年报分析工具")
    parser.add_argument("--action", 
                        choices=["download", "import", "list", "parse", "analyze", "text_analysis", 
                                "full_report", "compare", "detect_anomaly"],
                        required=True,
                        help="操作类型")
    parser.add_argument("--symbol", help="股票代码")
    parser.add_argument("--year", type=int, help="年报年份")
    parser.add_argument("--years", help="多个年份，逗号分隔")
    parser.add_argument("--local-path", help="本地 PDF 文件路径（用于 import 操作）")
    parser.add_argument("--output", choices=["json", "markdown"], default="json", help="输出格式")
    
    args = parser.parse_args()
    
    result = {}
    
    if args.action == "download":
        if not args.symbol or not args.year:
            print("Error: --symbol and --year are required for download")
            sys.exit(1)
        result = download_annual_report(args.symbol, args.year)
    
    elif args.action == "import":
        if not args.local_path or not args.symbol or not args.year:
            print("Error: --local-path, --symbol and --year are required for import")
            sys.exit(1)
        result = import_local_pdf(args.local_path, args.symbol, args.year)
    
    elif args.action == "list":
        result = list_local_reports(args.symbol)
    
    elif args.action == "parse":
        if not args.symbol or not args.year:
            print("Error: --symbol and --year are required for parse")
            sys.exit(1)
        result = parse_annual_report(args.symbol, args.year)
    
    elif args.action == "analyze":
        if not args.year:
            print("Error: --year is required for analyze")
            sys.exit(1)
        result = analyze_annual_report(args.symbol, args.year)
    
    elif args.action == "text_analysis":
        if not args.year:
            print("Error: --year is required for text_analysis")
            sys.exit(1)
        result = text_analysis(args.symbol, args.year)
    
    elif args.action == "full_report":
        if not args.year:
            print("Error: --year is required for full_report")
            sys.exit(1)
        result = full_report(args.symbol, args.year, args.output)
    
    elif args.action == "compare":
        if not args.years:
            print("Error: --years is required for compare")
            sys.exit(1)
        years = [int(y.strip()) for y in args.years.split(",")]
        result = compare_years(args.symbol, years)
    
    elif args.action == "detect_anomaly":
        if not args.years:
            if args.year:
                years = [args.year]
            else:
                print("Error: --years or --year is required")
                sys.exit(1)
        else:
            years = [int(y.strip()) for y in args.years.split(",")]
        
        # 获取分析数据
        analysis = analyze_annual_report(args.symbol, years[0])
        result = detect_financial_anomalies(analysis.get("indicators", {}), [])
    
    if args.output == "json" or isinstance(result, dict):
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    else:
        print(result)


if __name__ == "__main__":
    main()
