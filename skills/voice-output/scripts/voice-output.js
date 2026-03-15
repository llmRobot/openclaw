#!/usr/bin/env node
/**
 * voice-output.js - 语音输出工具 (Node.js 版本)
 * 
 * 使用方法:
 *   node voice-output.js --text "要朗读的文本"
 * 
 * 依赖:
 *   npm install edge-tts
 */

const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

// 默认配置
const DEFAULT_VOICE = 'zh-CN-XiaoxiaoNeural';
const DEFAULT_RATE = '+0%';
const DEFAULT_VOLUME = '+0%';

// 中文语音
const CHINESE_VOICES = {
  xiaoxiao: 'zh-CN-XiaoxiaoNeural',
  yunxi: 'zh-CN-YunxiNeural',
  yunjian: 'zh-CN-YunjianNeural',
  xiaoyi: 'zh-CN-XiaoyiNeural',
  yunxia: 'zh-CN-YunxiaNeural',
  yunfeng: 'zh-CN-YunfengNeural',
};

// 英文语音
const ENGLISH_VOICES = {
  jenny: 'en-US-JennyNeural',
  guy: 'en-US-GuyNeural',
  aria: 'en-US-AriaNeural',
};

// 获取共享目录
function getSharedVoiceDir() {
  // 容器内路径
  if (fs.existsSync('/home/node/.openclaw/workspace')) {
    return '/home/node/.openclaw/workspace/voice-output';
  }
  // 默认路径
  return path.join(process.env.HOME || '/tmp', '.openclaw/workspace/voice-output');
}

// 检测语言
function detectLanguage(text) {
  const chineseChars = (text.match(/[\u4e00-\u9fff]/g) || []).length;
  return chineseChars > text.length * 0.3 ? 'zh' : 'en';
}

// 选择语音
function selectVoice(voiceName, text) {
  if (voiceName) {
    if (CHINESE_VOICES[voiceName]) return CHINESE_VOICES[voiceName];
    if (ENGLISH_VOICES[voiceName]) return ENGLISH_VOICES[voiceName];
    return voiceName;
  }
  return detectLanguage(text) === 'zh' ? DEFAULT_VOICE : ENGLISH_VOICES.jenny;
}

// 生成语音
async function generateSpeech(text, options = {}) {
  const voice = selectVoice(options.voice, text);
  const rate = options.rate || DEFAULT_RATE;
  const volume = options.volume || DEFAULT_VOLUME;
  const outputDir = getSharedVoiceDir();
  
  // 确保目录存在
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }
  
  // 生成文件名
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
  const outputPath = path.join(outputDir, `voice_${timestamp}.mp3`);
  
  return new Promise((resolve, reject) => {
    // 使用 npx node-edge-tts
    const args = [
      '-y',
      'node-edge-tts',
      '-t', text,
      '-v', voice,
      '-f', outputPath
    ];
    
    const proc = spawn('npx', args, { stdio: 'inherit' });
    
    proc.on('close', (code) => {
      if (code === 0) {
        const stats = fs.statSync(outputPath);
        resolve({
          status: 'success',
          text_length: text.length,
          voice,
          audio_file: outputPath,
          file_size: stats.size,
          playback_mode: 'deferred',
          message: `语音已生成并保存到共享目录，等待播放: ${outputPath}`
        });
      } else {
        reject(new Error(`node-edge-tts exited with code ${code}`));
      }
    });
    
    proc.on('error', (err) => {
      reject(err);
    });
  });
}

// 主函数
async function main() {
  const args = process.argv.slice(2);
  
  let text = '';
  let voice = null;
  let rate = DEFAULT_RATE;
  let volume = DEFAULT_VOLUME;
  
  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case '--text':
        text = args[++i];
        break;
      case '--voice':
        voice = args[++i];
        break;
      case '--rate':
        rate = args[++i];
        break;
      case '--volume':
        volume = args[++i];
        break;
      case '--json':
        // 标记为 JSON 输出
        process.env.OUTPUT_JSON = '1';
        break;
    }
  }
  
  if (!text) {
    console.error('请提供要朗读的文本 (--text)');
    process.exit(1);
  }
  
  // 截断过长文本
  const maxLength = 5000;
  let truncated = false;
  if (text.length > maxLength) {
    text = text.slice(0, maxLength) + '...';
    truncated = true;
  }
  
  try {
    const result = await generateSpeech(text, { voice, rate, volume });
    if (truncated) result.truncated = true;
    
    if (process.env.OUTPUT_JSON === '1') {
      console.log(JSON.stringify(result, null, 2));
    } else {
      console.log(`✓ ${result.message}`);
    }
  } catch (err) {
    const errorResult = {
      status: 'error',
      message: err.message
    };
    
    if (process.env.OUTPUT_JSON === '1') {
      console.log(JSON.stringify(errorResult, null, 2));
    } else {
      console.error(`✗ ${err.message}`);
    }
    process.exit(1);
  }
}

main();
