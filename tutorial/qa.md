# Docker Compose 部署常见问题 (Q&A)

本文档总结了在使用 Docker Compose 部署 OpenClaw 时遇到的常见问题及解决方案。

---

## 目录

- [Gateway 启动失败](#gateway-启动失败)
- [Control UI 无法连接](#control-ui-无法连接)
- [设备配对问题](#设备配对问题)
- [认证被限流](#认证被限流)
- [API Key 配置错误](#api-key-配置错误)
- [Kimi 插件安装失败](#kimi-插件安装失败)
- [Kimi 鉴权失败 (HTTP 401)](#kimi-鉴权失败-http-401)
- [常用诊断命令](#常用诊断命令)

---

## Gateway 启动失败

### 问题表现

```bash
docker compose ps
# STATUS: Restarting (1) 47 seconds ago

docker compose logs openclaw-gateway
# Gateway failed to start: Error: non-loopback Control UI requires gateway.controlUi.allowedOrigins
```

### 原因

Gateway 使用 `lan` 绑定模式时，必须配置 `gateway.controlUi.allowedOrigins`，否则启动失败。

### 解决方案

**方法 1: 修改配置文件**

编辑 `~/.openclaw/openclaw.json`（或 `$OPENCLAW_CONFIG_DIR/openclaw.json`）：

```json
{
  "gateway": {
    "controlUi": {
      "allowedOrigins": [
        "http://127.0.0.1:18789",
        "http://localhost:18789"
      ]
    }
  }
}
```

**方法 2: 使用命令配置**

```bash
docker compose run --rm openclaw-cli config set gateway.controlUi.allowedOrigins '["http://127.0.0.1:18789"]' --strict-json
```

---

## Control UI 无法连接

### 问题表现

访问 http://127.0.0.1:18789/ 显示：
- `unauthorized: gateway token mismatch`
- `pairing required`
- `已断开与网关的连接`

### 原因 1: Token 未配置

需要在 Control UI 中输入 Gateway Token。

### 解决方案

1. 获取 Token:
   ```bash
   grep OPENCLAW_GATEWAY_TOKEN .env | cut -d= -f2
   ```

2. 打开 http://127.0.0.1:18789/

3. 在 **Access** 区域找到 **Gateway Token** 输入框，粘贴 Token

4. 点击 **Connect**

### 原因 2: 设备未配对

首次连接需要设备配对。

### 解决方案

```bash
# 查看待配对设备
docker compose run --rm openclaw-cli devices list

# 批准配对请求
docker compose run --rm openclaw-cli devices approve <request-id>
```

---

## 设备配对问题

### 问题表现

```
已断开与网关的连接。
pairing required
```

### 解决方案

```bash
# 1. 查看待配对请求
docker compose run --rm openclaw-cli devices list

# 输出示例:
# Pending (1)
# ┌──────────────────────────────────────┬──────────┐
# │ Request                              │ Role     │
# ├──────────────────────────────────────┼──────────┤
# │ 99acd98d-bd76-4e0c-80f4-3ed5c183b4d5 │ operator │
# └──────────────────────────────────────┴──────────┘

# 2. 批准请求
docker compose run --rm openclaw-cli devices approve 99acd98d-bd76-4e0c-80f4-3ed5c183b4d5

# 3. 刷新浏览器页面
```

---

## 认证被限流

### 问题表现

```
已断开与网关的连接。
unauthorized: too many failed authentication attempts (retry later)
```

### 原因

多次认证失败后，Gateway 会启用限流保护。

### 解决方案

重启 Gateway 重置限流状态：

```bash
docker compose restart openclaw-gateway
```

然后重新连接，确保使用正确的 Token。

---

## API Key 配置错误

### 问题表现

```bash
docker compose logs openclaw-gateway
# Config invalid
# Problem:
#   - auth.profiles.moonshot:default: Unrecognized key: "apiKey"
```

Gateway 无法启动。

### 原因

API Key 不应放在 `openclaw.json` 的 `auth.profiles` 中。正确的位置是 `auth-profiles.json`。

### 错误配置示例

```json
// ❌ 错误 - openclaw.json
{
  "auth": {
    "profiles": {
      "moonshot:default": {
        "provider": "moonshot",
        "mode": "api_key",
        "apiKey": "sk-xxx"  // ❌ 错误位置
      }
    }
  }
}
```

### 正确配置

**1. openclaw.json (只保留 profile 定义)**

```json
{
  "auth": {
    "profiles": {
      "moonshot:default": {
        "provider": "moonshot",
        "mode": "api_key"
      }
    }
  }
}
```

**2. auth-profiles.json (存储实际密钥)**

位置: `$OPENCLAW_CONFIG_DIR/agents/main/agent/auth-profiles.json`

```json
{
  "version": 1,
  "profiles": {
    "moonshot:default": {
      "type": "api_key",
      "provider": "moonshot",
      "key": "sk-xxx"
    }
  }
}
```

### 修复脚本

```python
import json

# 1. 清理 openclaw.json 中的错误配置
config_path = "/path/to/openclaw.json"
with open(config_path, "r") as f:
    config = json.load(f)

if "apiKey" in config.get("auth", {}).get("profiles", {}).get("moonshot:default", {}):
    del config["auth"]["profiles"]["moonshot:default"]["apiKey"]

with open(config_path, "w") as f:
    json.dump(config, f, indent=2)

# 2. 创建 auth-profiles.json
import os
auth_path = "/path/to/agents/main/agent/auth-profiles.json"
os.makedirs(os.path.dirname(auth_path), exist_ok=True)

auth_profiles = {
    "version": 1,
    "profiles": {
        "moonshot:default": {
            "type": "api_key",
            "provider": "moonshot",
            "key": "sk-xxx"
        }
    }
}

with open(auth_path, "w") as f:
    json.dump(auth_profiles, f, indent=2)
```

---

## Kimi 插件安装失败

### 问题表现

在宿主机运行安装脚本：

```bash
bash <(curl -fsSL https://cdn.kimi.com/kimi-claw/install.sh) --bot-token sk-xxx

# 错误输出:
# npm error g++: error: unrecognized command line option '-std=gnu++20'
# npm error make: *** [pty.target.mk:110: Release/obj.target/pty/src/unix/pty.o] Error 1
```

或者：

```bash
# 错误输出:
# [install-oss] ERROR: missing command: openclaw
# [install-oss] ERROR: install OpenClaw CLI then retry
```

### 原因

1. **宿主机 g++ 版本太旧**: 无法编译 `node-pty` 原生模块
2. **缺少 openclaw CLI**: 脚本需要本地 `openclaw` 命令

### 解决方案: 在容器内安装

```bash
# 在容器内运行安装脚本
docker compose run --rm --entrypoint bash openclaw-cli -c '
# 创建 wrapper 脚本
cat > /tmp/openclaw << "WRAPPER"
#!/bin/bash
node /app/dist/index.js "$@"
WRAPPER
chmod +x /tmp/openclaw

# 设置环境变量并运行安装
export OPENCLAW_BIN="/tmp/openclaw"
export TARGET_DIR="/home/node/.openclaw/extensions/kimi-claw"
export OPENCLAW_CONFIG_PATH="/home/node/.openclaw/openclaw.json"
bash <(curl -fsSL https://cdn.kimi.com/kimi-claw/install.sh) --bot-token sk-xxx
'

# 重启 Gateway 使插件生效
docker compose restart openclaw-gateway
```

### 验证安装

```bash
# 查看插件列表
docker compose run --rm openclaw-cli plugins list

# 查看日志确认连接
docker compose logs openclaw-gateway | grep kimi-bridge

# 应该看到:
# [kimi-bridge] [bridge-acp] connected
# [kimi-bridge] [im] subscribe connected
```

---

## 常用诊断命令

### 查看服务状态

```bash
docker compose ps -a
```

### 查看日志

```bash
# 实时日志
docker compose logs -f openclaw-gateway

# 最近 50 行
docker compose logs --tail=50 openclaw-gateway
```

### 检查配置

```bash
# 查看配置
docker compose run --rm openclaw-cli config get gateway

# 检查认证配置
docker compose run --rm openclaw-cli config get auth
```

### 进入容器调试

```bash
# 进入 CLI 容器
docker compose run --rm --entrypoint bash openclaw-cli

# 进入 Gateway 容器
docker compose exec openclaw-gateway bash
```

### 健康检查

```bash
# HTTP 健康检查
curl http://127.0.0.1:18789/healthz

# CLI 健康检查
docker compose exec openclaw-gateway node dist/index.js health --token "$OPENCLAW_GATEWAY_TOKEN"
```

### 重置环境

```bash
# 停止并删除容器
docker compose down

# 重新启动
docker compose up -d openclaw-gateway
```

---

## Kimi 鉴权失败 (HTTP 401)

### 问题表现

```
HTTP 401: Invalid Authentication 鉴权失败，请检查 apikey 是否正确
```

或在日志中看到：

```bash
docker compose logs openclaw-gateway | grep -i "401"
# embedded run agent end: runId=xxx isError=true error=HTTP 401: Invalid Authentication
```

### 原因

1. **Moonshot API Key 无效或过期** - Kimi 使用 Moonshot API，需要有效的 API Key
2. **API Key 格式错误** - Key 没有正确配置到 `auth-profiles.json`
3. **账户余额不足** - Moonshot 账户余额耗尽

### 诊断步骤

```bash
# 1. 检查当前配置的认证信息
docker compose run --rm openclaw-cli config get auth

# 2. 检查 API Key 是否配置
cat ~/.openclaw/agents/main/agent/auth-profiles.json

# 3. 查看详细日志
docker compose logs --tail=50 openclaw-gateway | grep -iE "auth|401|error"
```

### 解决方案

#### 方法 1: 更新 Moonshot API Key

1. 登录 [Moonshot 开放平台](https://platform.moonshot.cn/) 获取新 Key
2. 更新配置：

```bash
# 更新 API Key
docker compose run --rm openclaw-cli config set auth.profiles.moonshot:default.apiKey "sk-你的新key"

# 重启 Gateway
docker compose restart openclaw-gateway
```

#### 方法 2: 直接编辑 auth-profiles.json

```bash
# 编辑文件
nano ~/.openclaw/agents/main/agent/auth-profiles.json
```

确保格式正确：

```json
{
  "version": 1,
  "profiles": {
    "moonshot:default": {
      "type": "api_key",
      "provider": "moonshot",
      "key": "sk-你的有效key"
    }
  }
}
```

#### 方法 3: 使用其他模型提供商

如果 Moonshot Key 有问题，可以切换到其他模型：

```bash
# 配置 OpenAI
docker compose run --rm openclaw-cli config set auth.profiles.openai:default.apiKey "sk-xxx"

# 设置默认使用 OpenAI
docker compose run --rm openclaw-cli config set models.defaultProfile "openai:default"

# 重启
docker compose restart openclaw-gateway
```

### 验证修复

```bash
# 检查配置
docker compose run --rm openclaw-cli config get auth

# 测试发送消息（通过 Kimi 或 Control UI）
# 如果返回正常响应，说明鉴权成功
```

### 注意事项

- Moonshot API Key 格式为 `sk-` 开头
- 免费额度用完后需要充值
- 如果 Key 泄露，立即在平台重新生成

---

## 快速问题排查流程

```
1. 检查服务状态
   docker compose ps
   ↓
2. 查看日志
   docker compose logs openclaw-gateway
   ↓
3. 检查配置错误
   docker compose run --rm openclaw-cli config get gateway
   ↓
4. 检查 Token
   grep OPENCLAW_GATEWAY_TOKEN .env
   ↓
5. 检查设备配对
   docker compose run --rm openclaw-cli devices list
   ↓
6. 必要时重启
   docker compose restart openclaw-gateway
```

---

## 相关文档

- [Docker Compose 部署指南](./docker-compose-deployment.md)
- [官方文档 - Control UI](https://docs.openclaw.ai/web/control-ui)
- [官方文档 - Gateway 配置](https://docs.openclaw.ai/gateway/configuration)
