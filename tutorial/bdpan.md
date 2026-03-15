# 百度网盘技能 (bdpan-storage)

百度网盘文件管理工具，支持上传、下载、转存、分享、列表查询。

## 安装

### 方式一：自动安装（推荐）

告诉 OpenClaw：

```
下载此 skill 并解压安装：https://issuepcdn.baidupcs.com/issue/netdisk/ai-bdpan/skills/bdpan-storage-1.1.1.zip
```

### 方式二：手动安装

```bash
# 下载
curl -L -o bdpan-storage.zip https://issuepcdn.baidupcs.com/issue/netdisk/ai-bdpan/skills/bdpan-storage-1.1.1.zip

# 解压到技能目录
unzip bdpan-storage.zip -d ~/.openclaw/skills/
```

## 授权登录

安装后首次使用需要授权：

```bash
bash ~/.openclaw/skills/bdpan-storage/scripts/login.sh
```

登录流程：
1. 确认安全须知
2. 打开返回的授权链接
3. 在浏览器中扫码或登录百度账号
4. 复制 32 位授权码
5. 粘贴授权码完成绑定

## 使用方式

### 对话方式（推荐）

直接对 OpenClaw 说出需求：

| 示例 | 说明 |
|------|------|
| "查看百度网盘根目录" | 列出文件 |
| "上传 report.pdf 到百度网盘" | 上传文件 |
| "下载百度网盘里的 backup.zip" | 下载文件 |
| "分享百度网盘的 docs 文件夹" | 创建分享链接 |
| "转存这个链接到网盘：https://pan.baidu.com/s/xxx?pwd=abcd" | 转存分享 |

### 命令行方式

```bash
# 查看登录状态
bdpan whoami

# 列出文件
bdpan ls                    # 根目录
bdpan ls docs/              # 指定目录

# 上传
bdpan upload ./report.pdf report.pdf
bdpan upload ./project/ project/    # 文件夹需加 /

# 下载
bdpan download report.pdf ./
bdpan download backup/ ./backup/    # 文件夹需加 /

# 分享
bdpan share report.pdf
bdpan share file1.pdf file2.pdf     # 多文件分享

# 转存分享链接
bdpan transfer "https://pan.baidu.com/s/xxx?pwd=abcd"
bdpan transfer <链接> -p <提取码> -d my-folder/

# 从分享链接下载
bdpan download "https://pan.baidu.com/s/xxx?pwd=abcd" ./save/

# 注销
bdpan logout
```

## 功能详解

### 上传文件

```bash
bdpan upload <本地路径> <远程路径>
```

- 支持单文件和文件夹
- 文件夹路径需以 `/` 结尾
- 远程路径相对于 `/apps/bdpan/`

### 下载文件

```bash
bdpan download <远程路径> <本地路径>
```

- 支持从网盘直接下载
- 支持从分享链接下载

### 转存分享

```bash
bdpan transfer <分享链接> -p <提取码>
```

- 仅转存到网盘，不下载到本地
- 可指定目标目录 `-d`

### 创建分享

```bash
bdpan share <路径>
```

- 返回分享链接和提取码
- 支持多文件分享

## 路径说明

| 用户视角 | 实际路径 |
|---------|---------|
| 我的应用数据/bdpan/docs/ | /apps/bdpan/docs/ |

- 所有操作限制在 `/apps/bdpan/` 目录内
- 命令中使用 API 路径，展示时使用中文名

## 安全须知

> ⚠️ 公测阶段注意事项

1. **备份数据** - 使用前请备份网盘重要数据
2. **人工审核** - AI Agent 行为不可预测，请审核执行过程
3. **环境安全** - 严禁在公共环境扫码授权
4. **用完注销** - 公共环境使用后执行 `bdpan logout`
5. **保护凭证** - 切勿泄露配置文件和 Token

## 常见问题

### 登录失败

```bash
# 清除旧授权重新登录
bdpan logout
bash scripts/login.sh
```

### 路径错误

- 确保使用英文路径，不要用中文
- 文件夹路径需以 `/` 结尾
- 不要使用 `..` 或 `~`

### 上传/下载失败

- 检查网络连接
- 确认路径存在
- 查看磁盘空间

## 版本更新

```bash
bdpan update check     # 检查更新
bdpan update           # 执行更新
bdpan update rollback  # 回滚版本
```

## 相关链接

- [bdpan CLI 文档](https://github.com/bdpan-dev/bdpan-cli)
- [OpenClaw 技能开发指南](https://docs.openclaw.ai/skills)
