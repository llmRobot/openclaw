#!/usr/bin/env python3
"""
技能每日推送 - 推送到飞书

功能：
1. 获取每日技能报告
2. 通过飞书 API 推送到指定用户或群组

使用方法：
    python3 skill-push.py --test                    # 测试推送
    python3 skill-push.py --push                    # 执行推送
    python3 skill-push.py --setup <chat_id>         # 设置推送目标

配置文件: ~/.openclaw/workspace/skills/skill-discovery/push_config.json
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime

# 配置文件路径
CONFIG_DIR = os.path.expanduser("~/.openclaw/workspace/skills/skill-discovery")
PUSH_CONFIG_FILE = os.path.join(CONFIG_DIR, "push_config.json")

# 飞书 API 配置（从环境变量或配置文件读取）
FEISHU_API_BASE = "https://open.feishu.cn/open-apis"


def load_push_config() -> dict:
    """加载推送配置"""
    config = {
        "enabled": False,
        "feishu_app_id": "",
        "feishu_app_secret": "",
        "receive_id": "",  # 用户 open_id 或群组 chat_id
        "receive_id_type": "open_id",  # open_id, user_id, chat_id, email
        "push_time": "18:00",  # 北京时间
        "last_push": ""
    }
    
    # 加载已保存的配置
    if os.path.exists(PUSH_CONFIG_FILE):
        try:
            with open(PUSH_CONFIG_FILE, "r") as f:
                saved = json.load(f)
                config.update(saved)
        except:
            pass
    
    # 从 openclaw.json 读取飞书配置（如果未配置）
    if not config.get("feishu_app_id") or not config.get("feishu_app_secret"):
        openclaw_config_paths = [
            "/home/robot/agi/CLAW_DATA/config/openclaw.json",
            os.path.expanduser("~/.openclaw/openclaw.json"),
        ]
        
        for oc_path in openclaw_config_paths:
            if os.path.exists(oc_path):
                try:
                    with open(oc_path, "r") as f:
                        oc_config = json.load(f)
                        feishu_config = oc_config.get("channels", {}).get("feishu", {})
                        
                        if not config.get("feishu_app_id"):
                            config["feishu_app_id"] = feishu_config.get("appId", "") or feishu_config.get("accounts", {}).get("default", {}).get("appId", "")
                        
                        if not config.get("feishu_app_secret"):
                            config["feishu_app_secret"] = feishu_config.get("appSecret", "") or feishu_config.get("accounts", {}).get("default", {}).get("appSecret", "")
                        
                        if config.get("feishu_app_id") and config.get("feishu_app_secret"):
                            break
                except:
                    pass
    
    return config


def save_push_config(config: dict):
    """保存推送配置"""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(PUSH_CONFIG_FILE, "w") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get_feishu_token(app_id: str, app_secret: str) -> str:
    """获取飞书 tenant_access_token"""
    url = f"{FEISHU_API_BASE}/auth/v3/tenant_access_token/internal"
    
    data = json.dumps({
        "app_id": app_id,
        "app_secret": app_secret
    }).encode("utf-8")
    
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
            if result.get("code") == 0:
                return result.get("tenant_access_token", "")
            else:
                print(f"获取 token 失败: {result}", file=sys.stderr)
                return ""
    except Exception as e:
        print(f"请求失败: {e}", file=sys.stderr)
        return ""


def send_feishu_message(token: str, receive_id: str, receive_id_type: str, content: str) -> bool:
    """发送飞书消息"""
    url = f"{FEISHU_API_BASE}/im/v1/messages?receive_id_type={receive_id_type}"
    
    # 将 Markdown 内容包装成 JSON
    message_content = json.dumps({
        "zh_cn": {
            "title": "🤖 OpenClaw 每日技能推荐",
            "content": parse_markdown_to_feishu(content)
        }
    }, ensure_ascii=False)
    
    data = json.dumps({
        "receive_id": receive_id,
        "msg_type": "post",
        "content": message_content
    }).encode("utf-8")
    
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
            if result.get("code") == 0:
                print("消息发送成功!")
                return True
            else:
                print(f"发送失败: {result}", file=sys.stderr)
                return False
    except Exception as e:
        print(f"请求失败: {e}", file=sys.stderr)
        return False


def send_feishu_text_message(token: str, receive_id: str, receive_id_type: str, text: str) -> bool:
    """发送飞书文本消息"""
    url = f"{FEISHU_API_BASE}/im/v1/messages?receive_id_type={receive_id_type}"
    
    data = json.dumps({
        "receive_id": receive_id,
        "msg_type": "text",
        "content": json.dumps({"text": text}, ensure_ascii=False)
    }).encode("utf-8")
    
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
            if result.get("code") == 0:
                print("消息发送成功!")
                return True
            else:
                print(f"发送失败: {result}", file=sys.stderr)
                return False
    except Exception as e:
        print(f"请求失败: {e}", file=sys.stderr)
        return False


def parse_markdown_to_feishu(markdown: str) -> list:
    """将 Markdown 转换为飞书富文本格式"""
    # 简单转换，保持基本格式
    lines = markdown.split("\n")
    content = []
    
    for line in lines:
        if line.startswith("## "):
            # 标题转文本
            content.append([{"tag": "text", "text": line[3:] + "\n"}])
        elif line.startswith("### "):
            # 小标题
            content.append([{"tag": "text", "text": "\n" + line[4:] + "\n"}])
        elif line.startswith("- "):
            # 列表项
            text = line[2:]
            content.append([{"tag": "text", "text": "• " + text + "\n"}])
        elif line.startswith("```"):
            # 代码块 - 跳过
            continue
        elif line.startswith("# "):
            # 主标题
            content.append([{"tag": "text", "text": line[2:] + "\n"}])
        else:
            # 普通文本
            content.append([{"tag": "text", "text": line + "\n"}])
    
    return content


def generate_skill_report() -> str:
    """生成技能报告"""
    # 调用 discover_skills.py 生成报告
    script_path = os.path.join(os.path.dirname(__file__), "..", "skills", "skill-discovery", "scripts", "discover_skills.py")
    
    if not os.path.exists(script_path):
        # 使用默认内容
        return f"""## 🤖 OpenClaw 每日技能推荐

📅 {datetime.now().strftime('%Y年%m月%d日')}

### 🔥 热门技能

1. **Web Search** - 网页搜索能力
2. **PDF Tools** - PDF 处理工具
3. **Code Reviewer** - 代码审查助手
4. **Image Generator** - AI 图像生成
5. **Data Analyzer** - 数据分析工具

### 📦 安装命令

```
clawhub install <技能名称>
clawhub search "你的需求"
```

---
*数据来源: clawhub.ai, awesome-openclaw-skills*
"""
    
    # 执行脚本获取报告
    import subprocess
    try:
        result = subprocess.run(
            ["python3", script_path, "--type", "report", "--format", "markdown"],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            return result.stdout
    except Exception as e:
        print(f"生成报告失败: {e}", file=sys.stderr)
    
    return "技能报告生成失败，请稍后重试。"


def do_push(config: dict) -> bool:
    """执行推送"""
    if not config.get("enabled"):
        print("推送未启用，请先配置", file=sys.stderr)
        return False
    
    app_id = config.get("feishu_app_id", "")
    app_secret = config.get("feishu_app_secret", "")
    receive_id = config.get("receive_id", "")
    receive_id_type = config.get("receive_id_type", "open_id")
    
    if not all([app_id, app_secret, receive_id]):
        print("配置不完整，请检查飞书配置", file=sys.stderr)
        return False
    
    # 获取 token
    token = get_feishu_token(app_id, app_secret)
    if not token:
        print("获取飞书 token 失败", file=sys.stderr)
        return False
    
    # 生成报告
    report = generate_skill_report()
    
    # 发送消息
    success = send_feishu_text_message(token, receive_id, receive_id_type, report)
    
    if success:
        # 更新最后推送时间
        config["last_push"] = datetime.now().isoformat()
        save_push_config(config)
    
    return success


def main():
    parser = argparse.ArgumentParser(description="技能每日推送")
    parser.add_argument("--test", action="store_true", help="测试推送（使用配置文件）")
    parser.add_argument("--push", action="store_true", help="执行推送")
    parser.add_argument("--setup", nargs="?", const="interactive", help="设置推送目标")
    parser.add_argument("--set-receive-id", type=str, help="设置接收者 ID")
    parser.add_argument("--set-receive-type", type=str, choices=["open_id", "user_id", "chat_id", "email"], help="设置接收者类型")
    parser.add_argument("--show-config", action="store_true", help="显示当前配置")
    parser.add_argument("--enable", action="store_true", help="启用推送")
    parser.add_argument("--disable", action="store_true", help="禁用推送")
    
    args = parser.parse_args()
    
    config = load_push_config()
    
    # 从 openclaw.json 读取飞书配置
    openclaw_config_path = os.path.expanduser("~/.openclaw/openclaw.json")
    if os.path.exists(openclaw_config_path):
        try:
            with open(openclaw_config_path, "r") as f:
                oc_config = json.load(f)
                feishu_config = oc_config.get("channels", {}).get("feishu", {})
                if not config.get("feishu_app_id"):
                    config["feishu_app_id"] = feishu_config.get("appId", "")
                if not config.get("feishu_app_secret"):
                    config["feishu_app_secret"] = feishu_config.get("appSecret", "")
        except:
            pass
    
    if args.show_config:
        print("当前推送配置:")
        print(f"  启用状态: {'已启用' if config.get('enabled') else '未启用'}")
        print(f"  飞书 App ID: {config.get('feishu_app_id', '未配置')[:20]}...")
        print(f"  接收者 ID: {config.get('receive_id', '未配置')}")
        print(f"  接收者类型: {config.get('receive_id_type', 'open_id')}")
        print(f"  推送时间: {config.get('push_time', '18:00')}")
        print(f"  上次推送: {config.get('last_push', '从未推送')}")
        return
    
    if args.enable:
        config["enabled"] = True
        save_push_config(config)
        print("已启用推送")
        return
    
    if args.disable:
        config["enabled"] = False
        save_push_config(config)
        print("已禁用推送")
        return
    
    if args.set_receive_id:
        config["receive_id"] = args.set_receive_id
        save_push_config(config)
        print(f"已设置接收者 ID: {args.set_receive_id}")
        return
    
    if args.set_receive_type:
        config["receive_id_type"] = args.set_receive_type
        save_push_config(config)
        print(f"已设置接收者类型: {args.set_receive_type}")
        return
    
    if args.test:
        print("=== 测试推送 ===")
        report = generate_skill_report()
        print(report)
        return
    
    if args.push:
        success = do_push(config)
        sys.exit(0 if success else 1)
    
    if args.setup:
        print("=== 技能推送设置向导 ===")
        print(f"\n飞书 App ID: {config.get('feishu_app_id', '未配置')}")
        print(f"请设置接收推送的用户或群组:")
        print("  --set-receive-id <ID>      设置接收者 ID")
        print("  --set-receive-type <TYPE>  设置类型: open_id/user_id/chat_id/email")
        print("\n示例:")
        print("  python3 skill-push.py --set-receive-id ou_xxxx --set-receive-type open_id  # 私聊")
        print("  python3 skill-push.py --set-receive-id oc_xxxx --set-receive-type chat_id  # 群聊")
        return
    
    # 默认显示帮助
    parser.print_help()


if __name__ == "__main__":
    main()
