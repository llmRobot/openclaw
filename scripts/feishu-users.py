#!/usr/bin/env python3
"""
飞书用户/群组查询工具

获取飞书用户 ID 或群组 ID 用于推送配置
"""

import json
import os
import sys
import urllib.request

FEISHU_API_BASE = "https://open.feishu.cn/open-apis"


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
                print(f"获取 token 失败: {result}")
                return ""
    except Exception as e:
        print(f"请求失败: {e}")
        return ""


def get_bot_info(token: str) -> dict:
    """获取机器人信息"""
    url = f"{FEISHU_API_BASE}/bot/v3/info"
    
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result
    except Exception as e:
        print(f"获取机器人信息失败: {e}")
        return {}


def get_user_list(token: str, department_id: str = "0") -> list:
    """获取部门用户列表"""
    url = f"{FEISHU_API_BASE}/contact/v3/users?department_id={department_id}&page_size=50"
    
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
            if result.get("code") == 0:
                return result.get("data", {}).get("items", [])
    except Exception as e:
        print(f"获取用户列表失败: {e}")
    
    return []


def get_chat_list(token: str) -> list:
    """获取群组列表"""
    url = f"{FEISHU_API_BASE}/im/v1/chats?page_size=20"
    
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
            if result.get("code") == 0:
                return result.get("data", {}).get("items", [])
    except Exception as e:
        print(f"获取群组列表失败: {e}")
    
    return []


def main():
    # 从配置文件读取飞书配置
    config_paths = [
        "/home/robot/agi/CLAW_DATA/config/openclaw.json",
        os.path.expanduser("~/.openclaw/openclaw.json"),
        os.path.expanduser("~/agi/CLAW_DATA/config/openclaw.json"),
    ]
    
    config = None
    for config_path in config_paths:
        if os.path.exists(config_path):
            with open(config_path) as f:
                config = json.load(f)
            break
    
    if not config:
        print("错误: 未找到 OpenClaw 配置文件")
        sys.exit(1)
    
    feishu_config = config.get("channels", {}).get("feishu", {})
    app_id = feishu_config.get("appId", "")
    app_secret = feishu_config.get("appSecret", "")
    
    if not app_id or not app_secret:
        print("错误: 飞书配置不完整")
        sys.exit(1)
    
    # 获取 token
    print("获取飞书访问令牌...")
    token = get_feishu_token(app_id, app_secret)
    
    if not token:
        print("错误: 获取访问令牌失败")
        sys.exit(1)
    
    print("✅ 获取成功\n")
    
    # 获取机器人信息
    print("=== 机器人信息 ===")
    bot_info = get_bot_info(token)
    if bot_info.get("code") == 0:
        bot = bot_info.get("bot", {})
        print(f"名称: {bot.get('app_name', 'N/A')}")
        print(f"Open ID: {bot.get('open_id', 'N/A')}")
    print()
    
    # 获取群组列表
    print("=== 群组列表 ===")
    chats = get_chat_list(token)
    if chats:
        for i, chat in enumerate(chats, 1):
            print(f"{i}. {chat.get('name', 'N/A')}")
            print(f"   Chat ID: {chat.get('chat_id', 'N/A')}")
            print(f"   成员数: {chat.get('member_count', 'N/A')}")
            print()
    else:
        print("暂无群组\n")
    
    # 获取用户列表
    print("=== 用户列表 ===")
    users = get_user_list(token)
    if users:
        for i, user in enumerate(users[:10], 1):
            print(f"{i}. {user.get('name', 'N/A')}")
            print(f"   Open ID: {user.get('open_id', 'N/A')}")
            print(f"   User ID: {user.get('user_id', 'N/A')}")
            print()
    else:
        print("暂无用户信息（可能需要通讯录权限）\n")
    
    # 配置推送说明
    print("=== 配置推送 ===")
    print("选择一个接收推送的目标，然后运行以下命令：")
    print("")
    print("私聊推送:")
    print("  python3 /home/robot/agi/openclaw/scripts/skill-push.py --set-receive-id <open_id> --set-receive-type open_id --enable")
    print("")
    print("群聊推送:")
    print("  python3 /home/robot/agi/openclaw/scripts/skill-push.py --set-receive-id <chat_id> --set-receive-type chat_id --enable")


if __name__ == "__main__":
    main()
