#!/usr/bin/env python3
"""
语音输出技能 - 文本转语音播放
支持多种 TTS 引擎，可将文本通过本地音频设备播放出来
"""

import argparse
import asyncio
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

# 配置
DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"  # 微软 Edge TTS 中文女声
DEFAULT_RATE = "+0%"  # 语速调整
DEFAULT_VOLUME = "+0%"  # 音量调整

# 可用的中文语音
CHINESE_VOICES = {
    "xiaoxiao": "zh-CN-XiaoxiaoNeural",      # 女声，温柔
    "yunxi": "zh-CN-YunxiNeural",            # 男声，阳光
    "yunjian": "zh-CN-YunjianNeural",        # 男声，成熟
    "xiaoyi": "zh-CN-XiaoyiNeural",          # 女声，活泼
    "yunxia": "zh-CN-YunxiaNeural",          # 女声，儿童
    "yunfeng": "zh-CN-YunfengNeural",        # 男声，沉稳
}

# 可用的英文语音
ENGLISH_VOICES = {
    "jenny": "en-US-JennyNeural",            # 女声，自然
    "guy": "en-US-GuyNeural",                # 男声，成熟
    "aria": "en-US-AriaNeural",              # 女声，温柔
}


def check_dependencies():
    """检查依赖是否已安装"""
    missing = []
    
    try:
        import edge_tts
    except ImportError:
        missing.append("edge-tts")
    
    return missing


def install_dependencies():
    """安装缺失的依赖"""
    print("正在安装依赖...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "edge-tts", "-q"],
        check=True
    )
    print("依赖安装完成")


def get_audio_player():
    """获取可用的音频播放器"""
    # 优先使用 ffplay，因为它对 MP3 格式支持最好
    players = ["ffplay", "mpg123", "paplay", "aplay"]
    for player in players:
        result = subprocess.run(["which", player], capture_output=True)
        if result.returncode == 0:
            return player
    return None


def detect_language(text: str) -> str:
    """检测文本语言"""
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    if chinese_chars > len(text) * 0.3:
        return "zh"
    return "en"


def select_voice(voice_name: Optional[str], text: str) -> str:
    """选择合适的语音"""
    if voice_name:
        # 用户指定的语音名称
        if voice_name in CHINESE_VOICES:
            return CHINESE_VOICES[voice_name]
        if voice_name in ENGLISH_VOICES:
            return ENGLISH_VOICES[voice_name]
        # 直接使用用户提供的语音 ID
        return voice_name
    
    # 根据文本语言自动选择
    lang = detect_language(text)
    if lang == "zh":
        return DEFAULT_VOICE
    return ENGLISH_VOICES["jenny"]


async def text_to_speech_edge(
    text: str,
    output_file: str,
    voice: str = DEFAULT_VOICE,
    rate: str = DEFAULT_RATE,
    volume: str = DEFAULT_VOLUME
) -> bool:
    """使用 Edge TTS 将文本转换为语音"""
    try:
        import edge_tts
        
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
            rate=rate,
            volume=volume
        )
        
        await communicate.save(output_file)
        return True
    except Exception as e:
        print(f"TTS 转换失败: {e}", file=sys.stderr)
        return False


def play_audio(file_path: str, player: Optional[str] = None) -> bool:
    """播放音频文件"""
    if player is None:
        player = get_audio_player()
    
    if player is None:
        print("未找到可用的音频播放器", file=sys.stderr)
        return False
    
    try:
        if player == "paplay":
            subprocess.run([player, file_path], check=True, capture_output=True)
        elif player == "aplay":
            subprocess.run([player, file_path], check=True, capture_output=True)
        elif player == "mpg123":
            subprocess.run([player, "-q", file_path], check=True, capture_output=True)
        elif player == "ffplay":
            subprocess.run(
                [player, "-nodisp", "-autoexit", "-loglevel", "quiet", file_path],
                check=True
            )
        return True
    except subprocess.CalledProcessError as e:
        print(f"音频播放失败: {e}", file=sys.stderr)
        return False


def get_shared_voice_dir() -> str:
    """获取共享语音输出目录"""
    # 优先使用环境变量指定的目录
    env_dir = os.environ.get("VOICE_OUTPUT_DIR")
    if env_dir:
        return os.path.expanduser(env_dir)
    
    # 检查是否在 Docker 容器内（OpenClaw workspace 挂载）
    if os.path.exists("/home/node/.openclaw/workspace"):
        return "/home/node/.openclaw/workspace/voice-output"
    
    # 检查 OpenClaw 数据目录（宿主机）
    claw_data_dir = os.path.expanduser("~/agi/CLAW_DATA/ws")
    if os.path.exists(claw_data_dir):
        return os.path.join(claw_data_dir, "voice-output")
    
    # 默认使用本地 .openclaw 目录
    return os.path.expanduser("~/.openclaw/workspace/voice-output")


def speak(
    text: str,
    voice: Optional[str] = None,
    rate: str = DEFAULT_RATE,
    volume: str = DEFAULT_VOLUME,
    output_dir: Optional[str] = None,
    keep_file: bool = False,
    defer_playback: bool = True
) -> dict:
    """
    将文本转换为语音并播放
    
    Args:
        text: 要朗读的文本
        voice: 语音名称或ID
        rate: 语速调整 (如 "+20%", "-10%")
        volume: 音量调整
        output_dir: 输出目录（保存音频文件）
        keep_file: 是否保留音频文件
        defer_playback: 是否延迟播放（保存到共享目录，由宿主机服务播放）
    
    Returns:
        dict: 包含状态和结果信息
    """
    result = {
        "status": "error",
        "text_length": len(text),
        "voice": None,
        "audio_file": None,
        "message": ""
    }
    
    # 检查文本
    if not text or not text.strip():
        result["message"] = "文本为空"
        return result
    
    # 截断过长的文本
    max_length = 5000
    if len(text) > max_length:
        text = text[:max_length] + "..."
        result["truncated"] = True
        result["message"] = f"文本已截断至 {max_length} 字符"
    
    # 选择语音
    selected_voice = select_voice(voice, text)
    result["voice"] = selected_voice
    
    # 确定输出目录
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        audio_file = os.path.join(output_dir, "output.mp3")
    elif defer_playback:
        # 使用共享目录，文件名使用时间戳
        shared_dir = get_shared_voice_dir()
        os.makedirs(shared_dir, exist_ok=True)
        import time
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        audio_file = os.path.join(shared_dir, f"voice_{timestamp}.mp3")
        keep_file = True  # 保留文件让宿主机播放
    else:
        temp_dir = tempfile.mkdtemp()
        audio_file = os.path.join(temp_dir, "output.mp3")
    
    try:
        # 执行 TTS 转换
        success = asyncio.run(text_to_speech_edge(
            text=text,
            output_file=audio_file,
            voice=selected_voice,
            rate=rate,
            volume=volume
        ))
        
        if not success:
            result["message"] = "TTS 转换失败"
            return result
        
        # 检查音频文件
        if not os.path.exists(audio_file):
            result["message"] = "音频文件生成失败"
            return result
        
        file_size = os.path.getsize(audio_file)
        result["audio_file"] = audio_file
        result["file_size"] = file_size
        
        if defer_playback:
            # 延迟播放模式：保存到共享目录，由宿主机服务播放
            result["status"] = "success"
            result["message"] = f"语音已生成并保存到共享目录，等待播放: {audio_file}"
            result["playback_mode"] = "deferred"
        else:
            # 直接播放模式
            player = get_audio_player()
            if player:
                play_success = play_audio(audio_file, player)
                if play_success:
                    result["status"] = "success"
                    result["message"] = f"语音播放成功 (使用 {player})"
                    result["player"] = player
                else:
                    result["message"] = "音频播放失败"
            else:
                result["status"] = "success"
                result["message"] = f"音频文件已生成: {audio_file}（未找到播放器）"
        
    except Exception as e:
        result["message"] = f"发生错误: {str(e)}"
    finally:
        # 清理临时文件
        if not keep_file and os.path.exists(audio_file):
            try:
                os.remove(audio_file)
                if output_dir is None:
                    os.rmdir(os.path.dirname(audio_file))
            except:
                pass
    
    return result


def list_voices() -> dict:
    """列出可用的语音"""
    return {
        "status": "success",
        "chinese_voices": CHINESE_VOICES,
        "english_voices": ENGLISH_VOICES,
        "default": DEFAULT_VOICE
    }


def get_status() -> dict:
    """获取系统状态"""
    missing = check_dependencies()
    player = get_audio_player()
    
    return {
        "status": "ok" if not missing and player else "warning",
        "missing_dependencies": missing,
        "audio_player": player,
        "tts_engine": "edge-tts" if not missing else None
    }


def main():
    parser = argparse.ArgumentParser(description="语音输出工具")
    parser.add_argument(
        "--action",
        choices=["speak", "status", "voices", "install"],
        default="speak",
        help="操作类型"
    )
    parser.add_argument(
        "--text",
        type=str,
        help="要朗读的文本"
    )
    parser.add_argument(
        "--voice",
        type=str,
        help="语音名称（如 xiaoxiao, yunxi, jenny）或语音ID"
    )
    parser.add_argument(
        "--rate",
        type=str,
        default=DEFAULT_RATE,
        help="语速调整（如 +20%%, -10%%）"
    )
    parser.add_argument(
        "--volume",
        type=str,
        default=DEFAULT_VOLUME,
        help="音量调整（如 +50%%, -20%%）"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        help="音频文件输出目录"
    )
    parser.add_argument(
        "--keep-file",
        action="store_true",
        help="保留音频文件"
    )
    parser.add_argument(
        "--defer-playback",
        action="store_true",
        default=True,
        help="延迟播放模式：保存到共享目录，由宿主机服务播放（默认启用）"
    )
    parser.add_argument(
        "--direct-playback",
        action="store_true",
        help="直接播放模式：在本地播放音频"
    )
    parser.add_argument(
        "--file",
        type=str,
        help="从文件读取文本"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式输出"
    )
    
    args = parser.parse_args()
    
    if args.action == "install":
        install_dependencies()
        return
    
    if args.action == "status":
        result = get_status()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    
    if args.action == "voices":
        result = list_voices()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    
    if args.action == "speak":
        # 检查依赖
        missing = check_dependencies()
        if missing:
            print(f"缺少依赖: {', '.join(missing)}", file=sys.stderr)
            print("请运行: python3 voice_output.py --action install", file=sys.stderr)
            sys.exit(1)
        
        # 获取文本
        text = args.text
        if args.file:
            with open(args.file, 'r', encoding='utf-8') as f:
                text = f.read()
        
        if not text:
            print("请提供要朗读的文本（--text 或 --file）", file=sys.stderr)
            sys.exit(1)
        
        # 执行语音输出
        defer_playback = not args.direct_playback
        result = speak(
            text=text,
            voice=args.voice,
            rate=args.rate,
            volume=args.volume,
            output_dir=args.output_dir,
            keep_file=args.keep_file,
            defer_playback=defer_playback
        )
        
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            if result["status"] == "success":
                print(f"✓ {result['message']}")
            else:
                print(f"✗ {result['message']}", file=sys.stderr)
                sys.exit(1)


if __name__ == "__main__":
    main()
