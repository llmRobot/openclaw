# OpenClaw Docker 部署问题排查与解决方案

## 一、进入容器的方式

### 1. 进入 Gateway 容器

```bash
# 以交互方式进入 gateway 容器
docker compose exec openclaw-gateway bash

# 以 root 用户进入
docker compose exec --user root openclaw-gateway bash
```

### 2. 执行 CLI 命令

```bash
# 运行一次性命令
docker compose run --rm openclaw-cli <command>

# 示例
docker compose run --rm openclaw-cli config get gateway.mode
docker compose run --rm openclaw-cli devices list
docker compose run --rm openclaw-cli dashboard --no-open
```

### 3. 查看日志

```bash
# 实时查看日志
docker compose logs -f openclaw-gateway

# 查看最近 N 行日志
docker compose logs openclaw-gateway --tail 100
```

---

## 二、常见问题与解决方案

### 问题 1：kimi-claw 插件配置路径错误

**现象：**
```
[kimi-bridge] [im] subscribe disabled missing bot token
[kimi-bridge] [bridge-acp] auth failed (http 401), will not retry
```

**原因：**
配置路径错误。正确路径是 `plugins.entries.kimi-claw.config.bridge.token`（不是 `botToken`）。

**解决方案：**
```bash
# 正确配置方式
docker compose exec openclaw-gateway openclaw config set plugins.entries.kimi-claw.config.bridge.token 'your-bot-token'
docker compose restart openclaw-gateway
```

**验证连接成功：**
```bash
docker compose logs openclaw-gateway --tail 20 | grep "bridge-acp"
# 应看到: [kimi-bridge] [bridge-acp] connected
```

---

### 问题 2：本地镜像存在但脚本仍尝试 pull/build

**现象：**
```
==> Pulling Docker image: xxx
Error response from daemon: Head "https://registry-1.docker.io/..."
```

**原因：**
`docker-setup.sh` 脚本逻辑：
- `openclaw:local` → 强制本地构建
- 其他镜像名 → 执行 `docker pull`

脚本不会检查本地镜像是否存在。

**解决方案：**

修改 `docker-setup.sh`，添加本地镜像检查：

```bash
# 原代码 (约第413行)
if [[ "$IMAGE_NAME" == "openclaw:local" ]]; then
  echo "==> Building Docker image: $IMAGE_NAME"
  docker build ...
else
  echo "==> Pulling Docker image: $IMAGE_NAME"
  docker pull "$IMAGE_NAME"
fi

# 修改为
if docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
  echo "==> Using local Docker image: $IMAGE_NAME"
elif [[ "$IMAGE_NAME" == "openclaw:local" ]]; then
  echo "==> Building Docker image: $IMAGE_NAME"
  docker build ...
else
  echo "==> Pulling Docker image: $IMAGE_NAME"
  docker pull "$IMAGE_NAME"
fi
```

---

### 问题 2：Gateway 启动失败 - Missing config

**现象：**
```
Missing config. Run `openclaw setup` or set gateway.mode=local
```

**原因：**
配置文件中缺少 `gateway.mode` 设置。

**解决方案：**
```bash
docker compose run --rm openclaw-cli config set gateway.mode local
docker compose restart openclaw-gateway
```

---

### 问题 3：Gateway 启动失败 - allowedOrigins 未配置

**现象：**
```
Gateway failed to start: Error: non-loopback Control UI requires gateway.controlUi.allowedOrigins
```

**原因：**
`OPENCLAW_GATEWAY_BIND=lan` 时，需要明确允许访问来源。

**解决方案：**
```bash
docker compose run --rm openclaw-cli config set gateway.controlUi.allowedOrigins '["http://127.0.0.1:18789","http://localhost:18789"]' --strict-json
docker compose restart openclaw-gateway
```

---

### 问题 4：Web UI 显示 unauthorized / pairing required

**现象：**
```
unauthorized: gateway token missing
pairing required
origin not allowed
```

**原因：**
1. Token 未输入或无效
2. 浏览器设备未配对批准
3. 访问 origin 未在允许列表中

**解决方案：**

**步骤 1：获取 Dashboard URL（含 token）**
```bash
docker compose run --rm openclaw-cli dashboard --no-open
# 输出: http://127.0.0.1:18789/#token=xxxxxxx
```

**步骤 2：添加允许的 origin（如需要）**
```bash
docker compose run --rm openclaw-cli config set gateway.controlUi.allowedOrigins '["http://127.0.0.1:18789","http://localhost:18789"]' --strict-json
```

**步骤 3：查看待批准设备**
```bash
docker compose run --rm openclaw-cli devices list
```

**步骤 4：批准设备**
```bash
docker compose run --rm openclaw-cli devices approve <request-id>
```

---

## 三、完整启动流程

### 使用本地镜像启动

```bash
# 1. Tag 已有镜像
docker tag ghcr.io/openclaw/openclaw:latest openclaw:cached

# 2. 设置环境变量
export OPENCLAW_IMAGE=openclaw:cached
export OPENCLAW_CONFIG_DIR=/path/to/config
export OPENCLAW_WORKSPACE_DIR=/path/to/workspace
export OPENCLAW_HOME_VOLUME=openclaw-home
export OPENCLAW_EXTRA_MOUNTS="/host/path:/container/path"

# 3. 运行脚本
./docker-setup.sh
```

### 手动启动（跳过脚本）

```bash
# 1. 创建目录
mkdir -p "$OPENCLAW_CONFIG_DIR"/{identity,agents/main/agent,agents/main/sessions}
mkdir -p "$OPENCLAW_WORKSPACE_DIR"

# 2. 生成 token
echo "OPENCLAW_GATEWAY_TOKEN=$(openssl rand -hex 32)" >> .env

# 3. 启动
docker compose up -d openclaw-gateway

# 4. 配置
docker compose run --rm openclaw-cli config set gateway.mode local
docker compose run --rm openclaw-cli config set gateway.controlUi.allowedOrigins '["http://127.0.0.1:18789","http://localhost:18789"]' --strict-json


问题原因：kimi-claw 插件配置路径错误

❌ 错误：plugins.entries.kimi-claw.config.bridge.botToken
✅ 正确：plugins.entries.kimi-claw.config.bridge.token
解决命令：

docker compose exec openclaw-gateway openclaw config set plugins.entries.kimi-claw.config.bridge.token 'sk-V4SK7ZMIQQRUHGP2JDP7IVH7B4'
docker compose restart openclaw-gateway



```
# 5. 重启
docker compose restart openclaw-gateway

# 6. 获取访问链接
docker compose run --rm openclaw-cli dashboard --no-open
```

---

## 四、常用命令速查

| 操作 | 命令 |
|------|------|
| 查看容器状态 | `docker compose ps` |
| 查看日志 | `docker compose logs -f openclaw-gateway` |
| 进入容器 | `docker compose exec openclaw-gateway bash` |
| 重启服务 | `docker compose restart openclaw-gateway` |
| 停止服务 | `docker compose down` |
| 获取 token | `grep OPENCLAW_GATEWAY_TOKEN .env` |
| 获取 Dashboard URL | `docker compose run --rm openclaw-cli dashboard --no-open` |
| 查看设备列表 | `docker compose run --rm openclaw-cli devices list` |
| 批准设备 | `docker compose run --rm openclaw-cli devices approve <id>` |
| 健康检查 | `curl http://127.0.0.1:18789/healthz` |

---

## 五、配置文件位置

容器内：
- 配置文件：`/home/node/.openclaw/openclaw.json`
- 日志目录：`/tmp/openclaw/`

宿主机（通过 bind mount）：
- 配置目录：`$OPENCLAW_CONFIG_DIR`
- 工作空间：`$OPENCLAW_WORKSPACE_DIR`
