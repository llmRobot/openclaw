# Docker Compose 部署指南

本文档详细说明如何使用 Docker Compose 部署 OpenClaw。

## 目录

- [概述](#概述)
- [前置要求](#前置要求)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [服务说明](#服务说明)
- [高级配置](#高级配置)
- [Sandbox 隔离](#sandbox-隔离)
- [常用命令](#常用命令)
- [故障排查](#故障排查)

---

## 概述

OpenClaw 提供了完整的 Docker Compose 部署方案，包含两个核心服务：

- **openclaw-gateway**: OpenClaw 网关服务，负责消息路由和 agent 管理
- **openclaw-cli**: CLI 工具容器，用于执行管理命令

部署脚本 `docker-setup.sh` 自动处理镜像构建/拉取、配置初始化、权限修复和服务启动等流程。

---

## 前置要求

### 系统要求

- **操作系统**: Linux, macOS, 或 Windows (需支持 Docker)
- **Docker**: 20.10+ 
- **Docker Compose**: v2.0+ (Docker Compose Plugin)
- **内存**: 建议 4GB+ 可用内存
- **磁盘空间**: 建议 5GB+ 可用空间

### 验证环境

```bash
# 检查 Docker 版本
docker --version

# 检查 Docker Compose 版本
docker compose version

# 验证 Docker 运行
docker run --rm hello-world
```

---

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/openclaw/openclaw.git
cd openclaw
```

### 2. 运行安装脚本

```bash
./docker-setup.sh
```

该脚本会自动执行以下操作：

1. **构建或拉取镜像**: 默认构建 `openclaw:local` 镜像
2. **创建必要目录**: 配置目录和工作空间目录
3. **生成 Gateway Token**: 从配置读取或自动生成
4. **执行 Onboarding**: 交互式配置向导
5. **启动服务**: 启动 Gateway 和 CLI 服务
6. **配置 Sandbox** (可选): 如果设置了 `OPENCLAW_SANDBOX=1`

### 3. 验证部署

```bash
# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f openclaw-gateway

# 检查健康状态
docker compose exec openclaw-gateway node dist/index.js health --token "$OPENCLAW_GATEWAY_TOKEN"
```

---

## 配置说明

### 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `OPENCLAW_IMAGE` | `openclaw:local` | Docker 镜像名称，设为其他值时自动拉取而非构建 |
| `OPENCLAW_CONFIG_DIR` | `$HOME/.openclaw` | OpenClaw 配置目录 |
| `OPENCLAW_WORKSPACE_DIR` | `$HOME/.openclaw/workspace` | 工作空间目录 |
| `OPENCLAW_GATEWAY_PORT` | `18789` | Gateway 端口映射 |
| `OPENCLAW_BRIDGE_PORT` | `18790` | Bridge 端口映射 |
| `OPENCLAW_GATEWAY_BIND` | `lan` | Gateway 绑定模式 (`lan`/`loopback`) |
| `OPENCLAW_GATEWAY_TOKEN` | (自动生成) | Gateway 认证令牌 |
| `OPENCLAW_EXTENSIONS` | (空) | 构建时包含的扩展 (空格分隔) |
| `OPENCLAW_DOCKER_APT_PACKAGES` | (空) | 构建时安装的系统包 |
| `OPENCLAW_EXTRA_MOUNTS` | (空) | 额外的挂载点 (逗号分隔的 `source:target[:options]`) |
| `OPENCLAW_HOME_VOLUME` | (空) | Home 目录命名卷 |
| `OPENCLAW_SANDBOX` | (未设置) | 设为 `1`/`true` 启用 Sandbox 隔离 |
| `OPENCLAW_DOCKER_SOCKET` | `/var/run/docker.sock` | Docker socket 路径 (Sandbox 需要) |
| `OPENCLAW_INSTALL_DOCKER_CLI` | (空) | 构建时安装 Docker CLI (Sandbox 需要) |
| `OPENCLAW_ALLOW_INSECURE_PRIVATE_WS` | (空) | 允许不安全的私有 WebSocket |

### 配置示例

```bash
# 使用自定义配置目录和端口
OPENCLAW_CONFIG_DIR=/data/openclaw/config \
OPENCLAW_WORKSPACE_DIR=/data/openclaw/workspace \
OPENCLAW_GATEWAY_PORT=8080 \
./docker-setup.sh

# 启用 Sandbox 隔离
OPENCLAW_SANDBOX=1 ./docker-setup.sh

# 使用远程镜像并添加额外挂载
OPENCLAW_IMAGE=ghcr.io/openclaw/openclaw:latest \
OPENCLAW_EXTRA_MOUNTS="/data/projects:/home/node/projects,/tmp/scratch:/home/node/scratch" \
./docker-setup.sh
```

### .env 文件

脚本会自动生成 `.env` 文件，记录所有配置：

```bash
OPENCLAW_CONFIG_DIR=/home/user/.openclaw
OPENCLAW_WORKSPACE_DIR=/home/user/.openclaw/workspace
OPENCLAW_GATEWAY_PORT=18789
OPENCLAW_BRIDGE_PORT=18790
OPENCLAW_GATEWAY_BIND=lan
OPENCLAW_GATEWAY_TOKEN=abcdef123456...
OPENCLAW_IMAGE=openclaw:local
# ... 更多配置
```

---

## 服务说明

### openclaw-gateway

网关服务，负责：
- 接收和处理消息请求
- 管理 Agent 生命周期
- 处理命令路由和权限控制
- 提供健康检查端点

**关键配置**:
- **端口映射**: `${OPENCLAW_GATEWAY_PORT}:18789`, `${OPENCLAW_BRIDGE_PORT}:18790`
- **重启策略**: `unless-stopped`
- **健康检查**: 每 30 秒检查 `/healthz` 端点
- **绑定模式**: 通过 `--bind` 参数控制 (默认 `lan`)

### openclaw-cli

CLI 工具容器，用于：
- 执行 OpenClaw 命令 (`channels`, `config`, `agent` 等)
- 管理配置和频道
- 运行 onboarding 和诊断工具

**关键配置**:
- **网络模式**: `service:openclaw-gateway` (共享网关网络)
- **TTY/Stdin**: 支持交互式命令
- **安全限制**: 移除网络权限 (`NET_RAW`, `NET_ADMIN`)

---

## 高级配置

### 使用命名卷持久化

通过 `OPENCLAW_HOME_VOLUME` 使用 Docker 命名卷：

```bash
OPENCLAW_HOME_VOLUME=openclaw-home ./docker-setup.sh
```

这会创建一个命名卷 `openclaw-home`，挂载到容器的 `/home/node` 目录。

### 添加额外挂载

通过 `OPENCLAW_EXTRA_MOUNTS` 挂载额外目录：

```bash
OPENCLAW_EXTRA_MOUNTS="/data/projects:/home/node/projects,/tmp/scratch:/home/node/scratch" \
./docker-setup.sh
```

格式: `source:target[:options]` (逗号分隔，不支持空格)

### 自定义镜像构建

在构建镜像时添加扩展或系统包：

```bash
# 包含特定扩展
docker build \
  --build-arg OPENCLAW_EXTENSIONS="diagnostics-otel matrix" \
  -t openclaw:local \
  -f Dockerfile \
  .

# 安装额外的系统包
docker build \
  --build-arg OPENCLAW_DOCKER_APT_PACKAGES="python3 wget vim" \
  -t openclaw:local \
  -f Dockerfile \
  .
```

### 使用远程镜像

跳过本地构建，直接使用预构建镜像：

```bash
OPENCLAW_IMAGE=ghcr.io/openclaw/openclaw:latest ./docker-setup.sh
```

---

## Sandbox 隔离

Sandbox 隔离允许在独立的 Docker 容器中执行 agent 命令，提供更强的安全隔离。

### 启用 Sandbox

```bash
OPENCLAW_SANDBOX=1 ./docker-setup.sh
```

### 前置要求

1. **Docker CLI**: 镜像中需要安装 Docker CLI
   - 使用 `OPENCLAW_IMAGE=openclaw:local` 自动安装
   - 或构建时添加 `--build-arg OPENCLAW_INSTALL_DOCKER_CLI=1`
   
2. **Docker Socket**: 宿主机的 Docker socket 需要可访问
   - 默认路径: `/var/run/docker.sock`
   - 通过 `OPENCLAW_DOCKER_SOCKET` 自定义

### Sandbox 配置

启用后，脚本会自动配置：

```yaml
agents:
  defaults:
    sandbox:
      mode: "non-main"    # 非主进程在沙箱中运行
      scope: "agent"      # 沙箱范围是单个 agent
      workspaceAccess: "none"  # 沙箱无工作空间访问权限
```

### 安全机制

- 仅在验证 Docker CLI 可用后才挂载 Docker socket
- 通过 `group_add` 添加 Docker 组权限
- 配置失败时自动回滚，避免暴露 Docker socket

---

## 常用命令

### 服务管理

```bash
# 启动服务
docker compose up -d

# 停止服务
docker compose down

# 重启服务
docker compose restart openclaw-gateway

# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f openclaw-gateway
docker compose logs -f openclaw-cli
```

### 执行 CLI 命令

```bash
# 进入 CLI 容器
docker compose exec openclaw-cli bash

# 执行单条命令
docker compose run --rm openclaw-cli channels status
docker compose run --rm openclaw-cli config get gateway.mode

# Onboarding
docker compose run --rm openclaw-cli onboard --mode local --no-install-daemon
```

### 配置频道

```bash
# WhatsApp (QR 码登录)
docker compose run --rm openclaw-cli channels login

# Telegram (Bot Token)
docker compose run --rm openclaw-cli channels add --channel telegram --token <token>

# Discord (Bot Token)
docker compose run --rm openclaw-cli channels add --channel discord --token <token>
```

### 健康检查

```bash
# 检查 Gateway 健康状态
docker compose exec openclaw-gateway \
  node dist/index.js health --token "$OPENCLAW_GATEWAY_TOKEN"

# 使用 Docker Compose 健康检查
docker compose ps
```

---

## 故障排查

### 常见问题

#### 1. 权限错误

**症状**: 容器无法写入挂载目录

**解决方案**: 脚本会自动修复权限，但如仍有问题：

```bash
# 手动修复权限
docker compose run --rm --user root openclaw-cli \
  chown -R node:node /home/node/.openclaw
```

#### 2. Docker Socket 不可用

**症状**: Sandbox 启动失败，提示 "Docker socket not found"

**解决方案**:
```bash
# 检查 Docker socket 路径
ls -la /var/run/docker.sock

# 设置正确的 socket 路径
OPENCLAW_DOCKER_SOCKET=/var/run/docker.sock \
OPENCLAW_SANDBOX=1 \
./docker-setup.sh
```

#### 3. 镜像拉取失败

**症状**: 无法拉取远程镜像

**解决方案**:
```bash
# 使用本地构建
OPENCLAW_IMAGE=openclaw:local ./docker-setup.sh

# 或检查网络连接和镜像仓库访问权限
docker pull ghcr.io/openclaw/openclaw:latest
```

#### 4. 端口冲突

**症状**: 端口已被占用

**解决方案**:
```bash
# 更改端口映射
OPENCLAW_GATEWAY_PORT=8080 OPENCLAW_BRIDGE_PORT=8081 ./docker-setup.sh
```

### 调试技巧

```bash
# 查看容器日志
docker compose logs -f --tail=100 openclaw-gateway

# 进入容器调试
docker compose exec openclaw-cli bash

# 检查容器网络
docker network inspect openclaw_default

# 查看容器资源使用
docker stats
```

### 清理环境

```bash
# 停止并删除所有容器、网络
docker compose down

# 删除命名卷
docker volume rm openclaw_openclaw-home  # 如果使用了命名卷

# 完全清理（包括数据）
docker compose down -v
```

---

## 相关文档

- [官方文档](https://docs.openclaw.ai/install/docker)
- [频道配置](https://docs.openclaw.ai/channels)
- [Sandbox 隔离](https://docs.openclaw.ai/gateway/sandboxing)
- [Dockerfile 参考](../Dockerfile)
- [脚本源码](../docker-setup.sh)

---

## 支持

如遇到问题，请访问：
- [GitHub Issues](https://github.com/openclaw/openclaw/issues)
- [Discord 社区](https://discord.gg/openclaw)
