---
name: skill-discovery
description: 发现和推荐 OpenClaw 新技能。从 clawhub.ai、awesome-openclaw-skills、lobeHub 等渠道获取最新技能信息，支持每日推送。触发词：新技能、技能推荐、技能发现、技能推送、每日技能。
---

# 技能发现工具

## 功能概述

从多个渠道发现和推荐 OpenClaw 技能：
- **clawhub.ai** - 官方注册中心，13,700+ 技能
- **awesome-openclaw-skills** - 精选 2,868 个高质量技能，32 个类别
- **lobeHub** - 技能聚合平台，按安装量排序

## 使用方法

### 1. 获取每日技能报告

```bash
python3 /skills/skill-discovery/scripts/discover_skills.py --type report
```

### 2. 发现新技能

```bash
python3 /skills/skill-discovery/scripts/discover_skills.py --type new
```

### 3. 获取推荐技能

```bash
python3 /skills/skill-discovery/scripts/discover_skills.py --type recommend
```

### 4. 获取热门技能

```bash
python3 /skills/skill-discovery/scripts/discover_skills.py --type trending
```

### 5. 输出 Markdown 格式

```bash
python3 /skills/skill-discovery/scripts/discover_skills.py --type report --format markdown
```

## 输出示例

### 每日报告 (Markdown)

```markdown
## 🤖 OpenClaw 每日技能推荐

📅 2026年03月15日

### 🆕 新增技能
发现 5 个新技能！

- **AI Image Generator**: 生成 AI 图像
- **Code Reviewer**: 自动代码审查

### 🔥 热门技能 TOP 5
1. **Web Search** (50000 次安装): 网页搜索能力
2. **PDF Tools** (35000 次安装): PDF 处理工具

### 📦 安装命令
# 安装技能
clawhub install <技能名称>
```

## 数据来源

| 渠道 | 特点 |
|------|------|
| clawhub.ai | 官方注册中心，向量语义搜索 |
| awesome-openclaw-skills | 精选列表，已过滤恶意技能 |
| awesome-openclaw-skills-zh | 中文版，支持中文指令 |
| lobeHub | 另一个聚合平台，分类浏览 |
| skillsllm.com | 社区聚合，小众精品 |

## 注意事项

1. 首次运行会建立技能缓存
2. 后续运行会对比缓存发现新技能
3. 数据来源于公开 API，可能有速率限制
4. 推荐仅供参考，安装前请检查技能安全性
