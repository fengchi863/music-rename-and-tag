```markdown
# t2s-renamer（繁体→简体：文件名/文件夹名 + 音频标签）

一个 Windows 友好的小工具：递归遍历指定目录，把**文件夹名/文件名**中的繁体字转换为简体，并可选把音频文件的**元数据标签**（Title/Artist/Album 等）也从繁体改为简体。

- 文件名/文件夹名转换：OpenCC（t2s）
- 音频标签写入：mutagen（支持 flac/mp3/m4a/mp4/aac/ogg/opus/wav 等常见格式）

## 环境要求

- Python 3.9+

## 安装

在项目目录运行：

```bash
python -m pip install -r requirements.txt
```

如果你遇到 pip 网络/代理问题，可尝试（PowerShell）：

- 清空代理环境变量后安装：

```bash
powershell -NoProfile -Command "$env:HTTP_PROXY=''; $env:HTTPS_PROXY=''; $env:ALL_PROXY=''; python -m pip install -r requirements.txt"
```

- 国内网络使用镜像源：

```bash
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 使用方法

脚本入口：`rename_t2s.py`

### 1）先预演（强烈推荐）

只打印将要发生的改名/标签修改，不会真正写入：

```bash
python rename_t2s.py "D:\你的目录" --dry-run --update-tags
```

### 2）执行：改文件名/文件夹名（繁→简）

```bash
python rename_t2s.py "D:\你的目录"
```

### 3）执行：在改名基础上，同时改音频标签（Title/Artist/Album 等）

```bash
python rename_t2s.py "D:\你的目录" --update-tags
```

## 参数说明

- `root`：要处理的根目录（必填）
- `--dry-run`：预演，不落盘
- `--update-tags`：同时把音频文件标签从繁体转简体并写回
- `--no-sanitize-windows`：关闭 Windows 文件名合法化处理（不推荐）

## 行为与规则

- **自底向上改名**：先改子文件/子文件夹，再改父文件夹，避免路径变化导致找不到文件。
- **同名冲突处理**：转换后如果目标名已存在，会自动加 ` (1)`, ` (2)`…，避免覆盖。
- **Windows 文件名合法化（默认开启）**：
  - 替换非法字符 `\ / : * ? " < > |` 为 `_`
  - 去掉末尾的空格/点
  - 处理 Windows 保留名（CON/PRN/AUX/NUL/COM1…/LPT1…）

## 常见问题

### 1）终端里中文显示成乱码，但改名/标签实际成功？
这通常是控制台编码显示问题，不影响真实文件名与标签写入。请以资源管理器/播放器显示为准。

### 2）部分改名被跳过（skipped）？
常见原因：
- 文件/文件夹正在被占用（播放器正在播放、资源管理器预览占用等）
- 权限不足
- 目标名已存在（同名冲突）

建议关闭占用程序后重试，或先用 `--dry-run` 定位。

## 风险提示（请务必阅读）

- 批量重命名会影响播放器库、歌单路径、脚本引用路径等；建议先在小目录验证。
- 大范围操作前建议备份，或先 `--dry-run` 确认输出符合预期。
```

---

如果你愿意，我也可以再帮你补一份 `.gitignore` 和 `LICENSE(MIT)`，这样你直接初始化仓库就更标准了。
