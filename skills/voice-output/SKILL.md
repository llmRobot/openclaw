---
name: voice-output
description: |
  语音输出技能。将文本转换为语音并通过本地音频设备播放。支持中英文语音、语速调节、音量控制。适用于需要语音播报结果的场景，如年报分析结果朗读、通知提醒、无障碍访问等。
  触发关键词：语音播报、朗读、播放语音、TTS、读出来。
---

# 语音输出技能

## 概述

将文本转换为语音并通过本地音频设备播放，支持：
- **多语言支持**：中文、英文自动识别
- **多种语音**：微软 Edge TTS 高质量语音（免费）
- **参数调节**：语速、音量可调
- **Docker 支持**：延迟播放模式，支持容器环境

## 架构说明

由于 OpenClaw 通常运行在 Docker 容器中，而容器内无法直接播放音频，本技能采用**延迟播放模式**：

```
[容器内] → 生成音频文件 → [共享目录] → [宿主机播放服务] → 播放音频
```

## 快速开始

### 1. 安装依赖

```bash
# 安装 Python TTS 引擎
pip install edge-tts

# 安装音频播放器和文件监控工具（宿主机）
sudo apt install mpv inotify-tools
```

### 2. 启动播放服务

**方式一：前台运行（测试用）**
```bash
./scripts/voice-player.sh
```

**方式二：systemd 服务（推荐）**
```bash
# 复制服务文件
mkdir -p ~/.config/systemd/user/
cp scripts/voice-player.service ~/.config/systemd/user/

# 编辑服务文件中的路径
sed -i "s|%h|$HOME|g" ~/.config/systemd/user/voice-player.service

# 启用并启动服务
systemctl --user daemon-reload
systemctl --user enable voice-player
systemctl --user start voice-player

# 查看状态
systemctl --user status voice-player
```

### 3. 测试语音输出

```bash
# 在容器内或本地测试
python3 skills/voice-output/scripts/voice_output.py --text "测试语音输出"
```

## 使用方法

### 1. 检查系统状态

```bash
python3 /skills/voice-output/scripts/voice_output.py --action status
```

### 2. 语音播报文本

```bash
# 基本使用（延迟播放模式，默认）
python3 /skills/voice-output/scripts/voice_output.py --text "您好，这是一条测试消息"

# 指定语音
python3 /skills/voice-output/scripts/voice_output.py --text "分析报告已完成" --voice xiaoxiao

# 调整语速
python3 /skills/voice-output/scripts/voice_output.py --text "快速朗读测试" --rate "+50%"

# 直接播放模式（需要有音频设备）
python3 /skills/voice-output/scripts/voice_output.py --text "直接播放" --direct-playback
```

### 3. 从文件读取文本

```bash
python3 /skills/voice-output/scripts/voice_output.py --file /path/to/report.txt
```

### 4. 保存音频文件

```bash
# 保存到指定目录
python3 /skills/voice-output/scripts/voice_output.py \
  --text "这是一段将被保存的语音" \
  --output-dir ~/.openclaw/workspace/voice-output \
  --keep-file
```

### 5. 列出可用语音

```bash
python3 /skills/voice-output/scripts/voice_output.py --action voices
```

## 播放服务管理

```bash
# 查看服务状态
systemctl --user status voice-player

# 查看日志
journalctl --user -u voice-player -f

# 重启服务
systemctl --user restart voice-player

# 停止服务
systemctl --user stop voice-player
```

## 可用语音

### 中文语音

| 名称 | 描述 | 适用场景 |
|------|------|----------|
| `xiaoxiao` | 女声，温柔自然 | 通用播报、新闻朗读 |
| `yunxi` | 男声，阳光活力 | 科技资讯、教程 |
| `yunjian` | 男声，成熟稳重 | 商务报告、正式通知 |
| `xiaoyi` | 女声，活泼亲切 | 休闲内容、提示音 |
| `yunxia` | 女声，儿童音 | 儿童内容 |
| `yunfeng` | 男声，沉稳大气 | 专业分析、播客 |

### 英文语音

| 名称 | 描述 | 适用场景 |
|------|------|----------|
| `jenny` | 女声，自然流畅 | 通用播报 |
| `guy` | 男声，成熟 | 专业内容 |
| `aria` | 女声，温柔 | 轻松内容 |

## 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--action` | 操作类型: speak, status, voices, install | speak |
| `--text` | 要朗读的文本 | - |
| `--file` | 从文件读取文本 | - |
| `--voice` | 语音名称或ID | 自动选择 |
| `--rate` | 语速调整 (如 +20%, -10%) | +0% |
| `--volume` | 音量调整 (如 +50%) | +0% |
| `--output-dir` | 音频文件输出目录 | 临时文件 |
| `--keep-file` | 保留音频文件 | 否 |
| `--defer-playback` | 延迟播放模式（保存到共享目录） | 启用 |
| `--direct-playback` | 直接播放模式 | 禁用 |
| `--json` | JSON 格式输出 | 否 |

## 输出示例

### 成功响应

```json
{
  "status": "success",
  "text_length": 25,
  "voice": "zh-CN-XiaoxiaoNeural",
  "audio_file": "/home/node/.openclaw/workspace/voice-output/voice_20260314_220000.mp3",
  "file_size": 45678,
  "playback_mode": "deferred",
  "message": "语音已生成并保存到共享目录，等待播放"
}
```

### 状态检查

```json
{
  "status": "ok",
  "missing_dependencies": [],
  "audio_player": "mpv",
  "tts_engine": "edge-tts"
}
```

## 故障排除

### 播放服务未启动

```bash
# 检查服务状态
systemctl --user status voice-player

# 手动启动测试
./scripts/voice-player.sh
```

### 没有声音

1. 检查宿主机音频系统：
   ```bash
   # 测试播放
   mpv --no-video test.mp3
   
   # 检查 PulseAudio
   pactl info
   ```

2. 检查目录权限：
   ```bash
   ls -la ~/.openclaw/workspace/voice-output/
   ```

### 音频文件未生成

```bash
# 检查 edge-tts 安装
python3 -c "import edge_tts; print('OK')"

# 手动测试生成
python3 scripts/voice_output.py --text "测试" --json
```

## 与其他技能联动

### 与年报分析技能联动

```
# 1. 分析年报
使用 annual-report 技能生成分析报告

# 2. 语音播报结果
使用 voice-output 技能朗读关键指标
```

示例：
```bash
# 分析年报后，播报关键指标
python3 /skills/voice-output/scripts/voice_output.py \
  --text "深南电路2025年营收236亿元，同比增长32%，净利润32.8亿元，同比增长74.5%"
```

### 与产业链分析技能联动

```
# 1. 分析产业链
使用 industry-chain 技能生成分析结果

# 2. 语音播报摘要
使用 voice-output 技能朗读关键结论
```

## 使用场景

1. **无障碍访问**：为视障用户提供语音反馈
2. **驾车/运动场景**：解放双手，语音获取信息
3. **通知提醒**：重要事件语音提醒
4. **内容朗读**：长文本自动朗读
5. **报告播报**：分析结果语音输出

## 注意事项

1. 文本最大长度 5000 字符，超长文本会被截断
2. 首次使用需要安装 edge-tts 依赖
3. Docker 环境需要启动 `voice-player` 服务
4. 网络连接用于获取 Edge TTS 服务

## 技术细节

- **TTS 引擎**：微软 Edge TTS（免费、高质量）
- **音频格式**：MP3
- **播放器**：优先使用 mpv
- **语音采样**：24kHz 高质量音频
- **延迟播放**：通过 inotifywait 监控共享目录
