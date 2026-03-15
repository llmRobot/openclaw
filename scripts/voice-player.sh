#!/bin/bash
#
# voice-player.sh - 宿主机音频播放服务
# 监听共享目录中的音频文件并播放
#
# 使用方法:
#   ./scripts/voice-player.sh [--dir DIR] [--keep]
#
# 依赖:
#   - mpv (或 ffplay/ffprobe)
#   - inotifywait (inotify-tools 包)
#

set -e

# 默认配置
VOICE_DIR="${VOICE_DIR:-$HOME/.openclaw/workspace/voice-output}"
KEEP_FILES="${KEEP_FILES:-false}"
PLAYER="${PLAYER:-mpv}"
LOG_PREFIX="[voice-player]"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}${LOG_PREFIX}${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}${LOG_PREFIX}${NC} $1"
}

log_error() {
    echo -e "${RED}${LOG_PREFIX}${NC} $1" >&2
}

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --dir)
            VOICE_DIR="$2"
            shift 2
            ;;
        --keep)
            KEEP_FILES="true"
            shift
            ;;
        --help)
            echo "用法: $0 [--dir DIR] [--keep]"
            echo ""
            echo "选项:"
            echo "  --dir DIR   监听的目录 (默认: ~/.openclaw/workspace/voice-output)"
            echo "  --keep      保留播放过的音频文件"
            exit 0
            ;;
        *)
            log_error "未知参数: $1"
            exit 1
            ;;
    esac
done

# 检查依赖
check_dependencies() {
    local missing=()
    
    # 检查播放器
    if ! command -v mpv &> /dev/null; then
        if ! command -v ffplay &> /dev/null; then
            missing+=("mpv 或 ffplay")
        else
            PLAYER="ffplay"
        fi
    fi
    
    # 检查 inotifywait
    if ! command -v inotifywait &> /dev/null; then
        missing+=("inotifywait (inotify-tools)")
    fi
    
    if [ ${#missing[@]} -gt 0 ]; then
        log_error "缺少依赖: ${missing[*]}"
        log_error "请安装: sudo apt install mpv inotify-tools"
        exit 1
    fi
    
    log_info "使用播放器: $PLAYER"
}

# 播放音频文件
play_audio() {
    local file="$1"
    local basename=$(basename "$file")
    
    log_info "播放: $basename"
    
    # 获取文件大小
    local size=$(stat -c%s "$file" 2>/dev/null || echo "unknown")
    log_info "文件大小: $size bytes"
    
    # 播放音频
    if [ "$PLAYER" = "mpv" ]; then
        mpv --no-video --really-quiet "$file" 2>/dev/null
    else
        ffplay -nodisp -autoexit -loglevel quiet "$file" 2>/dev/null
    fi
    
    local result=$?
    if [ $result -eq 0 ]; then
        log_info "播放完成: $basename"
        
        # 删除文件（除非指定保留）
        if [ "$KEEP_FILES" != "true" ]; then
            rm -f "$file"
            log_info "已删除: $basename"
        fi
    else
        log_error "播放失败: $basename"
        # 移动到错误目录
        mkdir -p "${VOICE_DIR}/.failed"
        mv "$file" "${VOICE_DIR}/.failed/"
    fi
}

# 处理现有文件
process_existing_files() {
    log_info "检查现有音频文件..."
    
    for file in "${VOICE_DIR}"/*.mp3 "${VOICE_DIR}"/*.ogg "${VOICE_DIR}"/*.wav; do
        if [ -f "$file" ]; then
            # 检查文件是否已存在超过 5 秒（避免播放正在写入的文件）
            local age=$(( $(date +%s) - $(stat -c%Y "$file") ))
            if [ $age -gt 5 ]; then
                play_audio "$file"
            fi
        fi
    done
}

# 主监听循环
start_watcher() {
    # 确保目录存在
    mkdir -p "$VOICE_DIR"
    
    log_info "开始监听目录: $VOICE_DIR"
    log_info "按 Ctrl+C 停止"
    echo ""
    
    # 处理现有文件
    process_existing_files
    
    # 监听新文件
    inotifywait -m -e close_write -e moved_to --format '%f' "$VOICE_DIR" 2>/dev/null | while read filename; do
        # 检查是否是音频文件
        case "$filename" in
            *.mp3|*.ogg|*.wav|*.m4a|*.flac)
                # 等待文件完全写入
                sleep 0.5
                
                local filepath="${VOICE_DIR}/${filename}"
                if [ -f "$filepath" ]; then
                    play_audio "$filepath"
                fi
                ;;
            *)
                log_info "忽略非音频文件: $filename"
                ;;
        esac
    done
}

# 主函数
main() {
    log_info "=== 语音播放服务启动 ==="
    log_info "监听目录: $VOICE_DIR"
    log_info "保留文件: $KEEP_FILES"
    
    check_dependencies
    start_watcher
}

main
