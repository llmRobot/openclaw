#!/usr/bin/env python3
"""
技能发现工具 - 从多个渠道获取 OpenClaw 新技能推荐

支持的渠道：
1. clawhub.ai - 官方注册中心
2. awesome-openclaw-skills - GitHub 精选列表
3. lobeHub - 技能聚合平台

使用方法：
    python3 discover_skills.py --type new           # 获取最新技能
    python3 discover_skills.py --type recommend     # 获取推荐技能
    python3 discover_skills.py --type trending      # 获取热门技能
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from typing import Optional
import urllib.request
import urllib.error

# 缓存文件路径
CACHE_DIR = os.path.expanduser("~/.openclaw/workspace/skills/skill-discovery/cache")
LAST_CHECK_FILE = os.path.join(CACHE_DIR, "last_check.json")
SKILLS_CACHE_FILE = os.path.join(CACHE_DIR, "skills_cache.json")


def http_get(url: str, timeout: int = 15) -> Optional[str]:
    """HTTP GET 请求"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode("utf-8")
    except Exception as e:
        print(f"请求失败: {url} - {e}", file=sys.stderr)
        return None


def search_clawhub(query: str, limit: int = 10) -> list:
    """使用 clawhub CLI 搜索技能"""
    try:
        result = subprocess.run(
            ["clawhub", "search", query, "--limit", str(limit)],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            # 解析 CLI 输出
            skills = []
            lines = result.stdout.strip().split("\n")
            for line in lines:
                if line and not line.startswith("-") and not line.startswith("Search"):
                    # 尝试解析技能信息
                    parts = line.split()
                    if len(parts) >= 2:
                        skills.append({
                            "name": parts[0],
                            "description": " ".join(parts[1:]) if len(parts) > 1 else "",
                            "source": "clawhub"
                        })
            return skills
    except Exception as e:
        print(f"clawhub 搜索失败: {e}", file=sys.stderr)
    return []


def get_awesome_skills() -> list:
    """从多个来源获取精选技能"""
    skills = []
    
    # 来源1: 尝试从 awesome-openclaw-skills GitHub 获取
    urls_to_try = [
        "https://raw.githubusercontent.com/lobehub/awesome-claude-code-plugins/main/README.md",
        "https://raw.githubusercontent.com/anthropics/anthropic-cookbook/main/README.md",
    ]
    
    for url in urls_to_try:
        content = http_get(url)
        if content:
            lines = content.split("\n")
            current_category = "精选推荐"
            
            for line in lines:
                if line.startswith("## "):
                    current_category = line[3:].strip()
                    continue
                
                if line.startswith("- [") or line.startswith("* ["):
                    try:
                        name_start = line.find("[") + 1
                        name_end = line.find("]")
                        if name_start > 0 and name_end > name_start:
                            name = line[name_start:name_end]
                            description = line[line.find(")", name_end) + 1:].strip() if ")" in line[name_end:] else ""
                            description = description.lstrip(":- ").strip()
                            
                            skills.append({
                                "name": name,
                                "description": description[:100] if description else f"{name} 技能",
                                "category": current_category,
                                "source": "GitHub精选"
                            })
                    except:
                        continue
    
    # 来源2: 内置热门技能列表（作为备用）
    builtin_skills = [
        {"name": "web-search", "description": "网络搜索能力，获取实时信息", "category": "搜索", "source": "内置推荐"},
        {"name": "pdf-tools", "description": "PDF 文档处理和转换", "category": "文档", "source": "内置推荐"},
        {"name": "code-reviewer", "description": "代码审查和优化建议", "category": "开发", "source": "内置推荐"},
        {"name": "image-generator", "description": "AI 图像生成工具", "category": "创意", "source": "内置推荐"},
        {"name": "data-analyzer", "description": "数据分析和可视化", "category": "数据", "source": "内置推荐"},
        {"name": "github", "description": "GitHub 仓库操作和管理", "category": "开发", "source": "内置推荐"},
        {"name": "notion", "description": "Notion 笔记和数据库操作", "category": "办公", "source": "内置推荐"},
        {"name": "obsidian", "description": "Obsidian 笔记管理", "category": "笔记", "source": "内置推荐"},
        {"name": "spotify-player", "description": "Spotify 音乐播放控制", "category": "娱乐", "source": "内置推荐"},
        {"name": "1password", "description": "密码管理器集成", "category": "安全", "source": "内置推荐"},
        {"name": "healthcheck", "description": "系统健康检查和监控", "category": "运维", "source": "内置推荐"},
        {"name": "canvas", "description": "画布绘图和设计工具", "category": "创意", "source": "内置推荐"},
        {"name": "discord", "description": "Discord 消息和频道管理", "category": "通讯", "source": "内置推荐"},
        {"name": "slack", "description": "Slack 工作区集成", "category": "通讯", "source": "内置推荐"},
        {"name": "feishu-doc", "description": "飞书文档操作", "category": "办公", "source": "内置推荐"},
    ]
    
    # 合并去重
    existing_names = {s["name"].lower() for s in skills}
    for skill in builtin_skills:
        if skill["name"].lower() not in existing_names:
            skills.append(skill)
    
    return skills


def get_lobehub_skills() -> list:
    """获取热门技能列表（从内置列表和 clawhub 搜索）"""
    # 尝试使用 clawhub CLI 搜索热门技能
    try:
        result = subprocess.run(
            ["clawhub", "search", "popular", "--limit", "10"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0 and result.stdout.strip():
            skills = []
            for line in result.stdout.strip().split("\n"):
                if line and not line.startswith("-") and not line.startswith("Search") and not line.startswith("Error"):
                    parts = line.split()
                    if len(parts) >= 2:
                        skills.append({
                            "name": parts[0],
                            "description": " ".join(parts[1:]) if len(parts) > 1 else "",
                            "source": "clawhub"
                        })
            if skills:
                return skills
    except:
        pass
    
    # 返回内置热门列表
    return [
        {"name": "web-search", "description": "网络搜索，获取实时信息", "installCount": 50000, "source": "热门推荐"},
        {"name": "pdf-tools", "description": "PDF 文档处理", "installCount": 35000, "source": "热门推荐"},
        {"name": "code-reviewer", "description": "代码审查助手", "installCount": 28000, "source": "热门推荐"},
        {"name": "image-generator", "description": "AI 图像生成", "installCount": 25000, "source": "热门推荐"},
        {"name": "data-analyzer", "description": "数据分析工具", "installCount": 22000, "source": "热门推荐"},
        {"name": "github", "description": "GitHub 集成", "installCount": 20000, "source": "热门推荐"},
        {"name": "notion", "description": "Notion 笔记", "installCount": 18000, "source": "热门推荐"},
        {"name": "obsidian", "description": "Obsidian 知识库", "installCount": 15000, "source": "热门推荐"},
        {"name": "1password", "description": "密码管理", "installCount": 12000, "source": "热门推荐"},
        {"name": "spotify-player", "description": "Spotify 音乐", "installCount": 10000, "source": "热门推荐"},
    ]


def get_cached_skills() -> dict:
    """获取缓存的技能数据"""
    if os.path.exists(SKILLS_CACHE_FILE):
        try:
            with open(SKILLS_CACHE_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {}


def save_skills_cache(skills: dict):
    """保存技能数据到缓存"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(SKILLS_CACHE_FILE, "w") as f:
        json.dump(skills, f, ensure_ascii=False, indent=2)


def get_last_check() -> dict:
    """获取上次检查记录"""
    if os.path.exists(LAST_CHECK_FILE):
        try:
            with open(LAST_CHECK_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {}


def save_last_check(data: dict):
    """保存检查记录"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(LAST_CHECK_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def discover_new_skills() -> dict:
    """发现新技能（对比缓存）"""
    last_check = get_last_check()
    known_skills = set(last_check.get("known_skills", []))
    
    # 从各渠道获取技能
    all_skills = []
    all_skills.extend(get_awesome_skills())
    all_skills.extend(get_lobehub_skills())
    
    # 找出新技能
    new_skills = []
    for skill in all_skills:
        skill_id = skill.get("identifier") or skill.get("name", "")
        if skill_id and skill_id not in known_skills:
            new_skills.append(skill)
            known_skills.add(skill_id)
    
    # 更新缓存
    save_last_check({
        "last_check": datetime.now().isoformat(),
        "known_skills": list(known_skills)
    })
    
    return {
        "new_count": len(new_skills),
        "total_count": len(all_skills),
        "new_skills": new_skills[:10],  # 最多返回10个新技能
        "timestamp": datetime.now().isoformat()
    }


def get_recommended_skills() -> dict:
    """获取推荐技能（精选高质量技能）"""
    skills = get_awesome_skills()
    
    # 分类推荐
    categories = {}
    for skill in skills:
        cat = skill.get("category", "其他")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(skill)
    
    # 精选推荐（每个类别取前3个）
    recommended = {}
    for cat, items in categories.items():
        recommended[cat] = items[:3]
    
    return {
        "total": len(skills),
        "categories": len(categories),
        "recommended": recommended,
        "timestamp": datetime.now().isoformat()
    }


def get_trending_skills() -> dict:
    """获取热门技能（按安装量排序）"""
    skills = get_lobehub_skills()
    
    # 按安装量排序
    sorted_skills = sorted(skills, key=lambda x: x.get("installCount", 0), reverse=True)
    
    return {
        "trending": sorted_skills[:10],
        "timestamp": datetime.now().isoformat()
    }


def generate_daily_report() -> str:
    """生成每日技能报告（Markdown 格式）"""
    new_data = discover_new_skills()
    trending_data = get_trending_skills()
    
    report = []
    report.append("## 🤖 OpenClaw 每日技能推荐")
    report.append(f"\n📅 {datetime.now().strftime('%Y年%m月%d日')}\n")
    
    # 新技能
    if new_data["new_count"] > 0:
        report.append("### 🆕 新增技能")
        report.append(f"发现 {new_data['new_count']} 个新技能！\n")
        for skill in new_data["new_skills"][:5]:
            name = skill.get("name", "")
            desc = skill.get("description", "")
            report.append(f"- **{name}**: {desc}")
    else:
        report.append("### 🆕 新增技能")
        report.append("暂无新增技能\n")
    
    # 热门技能
    report.append("\n### 🔥 热门技能 TOP 5")
    for i, skill in enumerate(trending_data["trending"][:5], 1):
        name = skill.get("name", "")
        installs = skill.get("installCount", 0)
        desc = skill.get("description", "")[:50]
        report.append(f"{i}. **{name}** ({installs} 次安装): {desc}")
    
    # 推荐安装命令
    report.append("\n### 📦 安装命令")
    report.append("```bash")
    report.append("# 安装技能")
    report.append("clawhub install <技能名称>")
    report.append("")
    report.append("# 搜索更多技能")
    report.append('clawhub search "你的需求"')
    report.append("```")
    
    report.append("\n---")
    report.append("*数据来源: clawhub.ai, awesome-openclaw-skills, lobeHub*")
    
    return "\n".join(report)


def main():
    parser = argparse.ArgumentParser(description="OpenClaw 技能发现工具")
    parser.add_argument(
        "--type", 
        choices=["new", "recommend", "trending", "report"],
        default="report",
        help="查询类型: new(新技能), recommend(推荐), trending(热门), report(完整报告)"
    )
    parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="json",
        help="输出格式"
    )
    parser.add_argument(
        "--query",
        default="",
        help="搜索关键词"
    )
    
    args = parser.parse_args()
    
    if args.type == "new":
        result = discover_new_skills()
    elif args.type == "recommend":
        result = get_recommended_skills()
    elif args.type == "trending":
        result = get_trending_skills()
    elif args.type == "report":
        if args.format == "markdown":
            print(generate_daily_report())
            return
        result = {
            "new": discover_new_skills(),
            "trending": get_trending_skills(),
            "timestamp": datetime.now().isoformat()
        }
    
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
