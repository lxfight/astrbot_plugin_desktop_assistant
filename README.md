# 🖥️ AstrBot 桌面助手插件

[![GitHub](https://img.shields.io/badge/GitHub-muyouzhi6-blue?logo=github)](https://github.com/muyouzhi6)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![AstrBot](https://img.shields.io/badge/AstrBot-v4.0+-purple.svg)](https://github.com/Soulter/AstrBot)

为 AstrBot 提供桌面悬浮球助手功能的平台适配器插件。

> ⚠️ **重要提示**：本插件需要配合桌面客户端一起使用！
> 
> 👉 **配套客户端**：[Astrbot-desktop-assistant](https://github.com/muyouzhi6/Astrbot-desktop-assistant)

## 🎯 项目概述

本项目是 AstrBot 桌面助手的**服务端插件部分**，作为 AstrBot 的平台适配器运行，处理来自桌面客户端的消息。

### 架构说明

```
┌─────────────────────────────────────────────────────────────┐
│                      用户桌面                                │
│  ┌─────────────────────────────────────────────────────┐   │
│  │           AstrBot 桌面助手客户端 (配套项目)           │   │
│  │  • 悬浮球界面                                         │   │
│  │  • 对话窗口                                          │   │
│  │  • 截图功能                                          │   │
│  └────────────────────────┬────────────────────────────┘   │
│                           │ HTTP API                        │
│                           ▼                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │            AstrBot 服务器 + 本插件                    │   │
│  │  • WebChat 平台适配器                                │   │
│  │  • 消息队列管理                                      │   │
│  │  • AI 对话处理                                       │   │
│  │  • 主动对话服务                                      │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## ✨ 功能特性

### 🎈 悬浮球
- **可拖拽设计**：随意拖动到屏幕任意位置
- **自定义外观**：支持设置大小（32-128px）、透明度和自定义头像
- **智能交互**：
  - 单击：显示气泡消息
  - 双击：打开对话窗口
  - 右键：显示功能菜单
- **动态效果**：收到新消息时悬浮球呼吸动画提示

### 💬 对话窗口
- **多模态输入**：支持文字、图片、语音、文件
- **截图功能**：区域截图和全屏截图
- **语音录制**：按住录音，松开发送
- **流式显示**：实时显示 AI 回复
- **消息气泡**：美观的聊天界面
- **图片预览**：点击图片查看大图，支持缩放、复制、下载

### 🖥️ 桌面监控
- **自动截屏**：定时捕获桌面状态
- **智能清理**：自动管理截图存储空间
- **隐私保护**：所有数据仅保存在本地

### 💡 主动对话
- **随机问候**：AI 主动发起对话
- **窗口感知**：检测活动窗口变化并作出响应
- **定时提醒**：在特定时间段发送问候
- **桌面感知**：基于截图内容进行智能对话

### ⚙️ 系统托盘
- **后台运行**：最小化到系统托盘
- **快捷操作**：托盘菜单快速访问所有功能
- **状态同步**：与悬浮球状态保持一致

### 🚀 其他功能
- **开机自启动**：支持 Windows 开机自动启动
- **主题切换**：亮色/暗色/跟随系统

## 📦 快速开始

### 1. 安装插件

```bash
# 方式1: 通过 AstrBot 插件市场搜索 "desktop_assistant"

# 方式2: 手动克隆到插件目录
git clone https://github.com/muyouzhi6/astrbot_plugin_desktop_assistant.git \
    data/plugins/astrbot_plugin_desktop_assistant
```

### 2. 安装依赖

```bash
cd data/plugins/astrbot_plugin_desktop_assistant
pip install -r requirements.txt
```

### 3. 安装桌面客户端

```bash
# 克隆客户端项目
git clone https://github.com/muyouzhi6/Astrbot-desktop-assistant.git
cd Astrbot-desktop-assistant

# 安装依赖
pip install -r requirements.txt

# 启动客户端
python -m desktop_client
```

### 4. 配置连接

1. 启动 AstrBot 服务器
2. 启动桌面客户端
3. 在客户端设置中配置服务器地址（默认 `http://localhost:6185`）
4. 输入 AstrBot 的用户名和密码
5. 测试连接

## 📋 依赖列表

| 依赖 | 版本 | 说明 |
|------|------|------|
| PySide6 | ≥6.5.0 | Qt6 GUI 框架 |
| mss | ≥9.0.0 | 截图服务 |
| pyaudio | ≥0.2.13 | 音频录制 |
| pillow | ≥10.0.0 | 图像处理 |

### 可选依赖

```bash
# Windows 音频支持（如果 pyaudio 安装失败）
pip install pipwin
pipwin install pyaudio
```

## 🎮 使用指南

### 基本操作

1. **打开对话**：双击悬浮球或右键菜单选择"打开对话"
2. **发送消息**：在对话窗口输入文字后按 Enter 或点击发送按钮
3. **发送图片**：点击 📷 按钮选择图片，或直接拖拽图片到对话窗口
4. **截图发送**：点击 ✂️ 进行区域截图，或 🖥️ 进行全屏截图
5. **语音输入**：长按 🎤 按钮录音，松开后自动发送
6. **隐藏悬浮球**：右键菜单选择"隐藏悬浮球"，可从托盘图标恢复

### 设置配置

右键悬浮球或点击托盘菜单中的"设置"打开设置窗口：

#### 外观设置
- **悬浮球大小**：32-128 像素
- **透明度**：10%-100%
- **自定义头像**：选择本地图片作为悬浮球头像

#### 对话窗口设置
- **窗口尺寸**：宽度 300-1200px，高度 400-1200px
- **字体大小**：10-24pt

#### 桌面监控设置
- **启用开关**：开启/关闭桌面监控
- **监控间隔**：10-600 秒
- **截图保留**：最大数量和保留时长

#### 主动对话设置
- **启用开关**：开启/关闭主动对话
- **触发概率**：随机触发的概率
- **时间间隔**：最小/最大对话间隔
- **窗口变化触发**：检测到窗口变化时触发对话
- **定时问候**：在特定时间段发送问候

#### 其他设置
- **语音播放**：启用/禁用 TTS
- **开机自启**：Windows 开机时自动启动

## ⌨️ 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Enter` | 发送消息 |
| `Shift + Enter` | 消息换行 |
| `Ctrl + V` | 粘贴图片 |
| `Esc` | 关闭对话窗口 |

## 📁 目录结构

```
astrbot_plugin_desktop_assistant/
├── main.py                 # 插件入口，Platform 适配器
├── metadata.yaml           # 插件元数据
├── requirements.txt        # Python 依赖
├── README.md              # 使用文档（本文件）
├── gui/                   # GUI 模块
│   ├── app.py            # Qt 应用主类
│   ├── settings_window.py # 设置窗口
│   ├── system_tray.py    # 系统托盘
│   ├── screenshot_selector.py # 截图选择器
│   ├── floating_ball/    # 悬浮球组件
│   │   └── ball_window.py
│   ├── chat_window/      # 对话窗口组件
│   │   └── chat_window.py
│   └── resources/        # 资源文件
│       └── styles.qss
├── services/              # 后台服务
│   ├── screen_capture.py  # 截图服务
│   ├── audio_recorder.py  # 音频录制
│   ├── desktop_monitor.py # 桌面监控
│   └── proactive_dialog.py # 主动对话
└── models/                # 数据模型
    └── __init__.py
```

## ❓ 常见问题

### Q: 悬浮球不显示？
A: 检查以下几点：
1. 确保 PySide6 已正确安装
2. 查看 AstrBot 日志是否有错误信息
3. 尝试从系统托盘恢复悬浮球显示

### Q: 截图功能无法使用？
A: 确保已安装 `mss` 库：
```bash
pip install mss
```

### Q: 语音录制无法使用？
A: 确保已安装 `pyaudio`：
```bash
# Windows
pip install pipwin
pipwin install pyaudio

# Linux
sudo apt-get install portaudio19-dev
pip install pyaudio

# macOS
brew install portaudio
pip install pyaudio
```

### Q: 设置保存后不生效？
A: 部分设置（如悬浮球大小、透明度）需要重启应用后才能生效。

### Q: 如何完全退出？
A: 右键悬浮球或托盘图标，选择"退出"。

### Q: 主动对话太频繁？
A: 在设置中调低触发概率或增加最小间隔时间。

### Q: 桌面监控会泄露隐私吗？
A: 不会。所有截图仅保存在本地临时目录，不会上传到任何服务器。截图会根据设置的保留策略自动清理。

### Q: 客户端无法连接服务器？
A: 检查以下几点：
1. 确认 AstrBot 服务器正在运行
2. 确认服务器地址配置正确
3. 确认防火墙未阻止连接
4. 检查用户名密码是否正确

## 🔗 相关链接

- **配套客户端**: [Astrbot-desktop-assistant](https://github.com/muyouzhi6/Astrbot-desktop-assistant)
- **AstrBot**: [https://github.com/Soulter/AstrBot](https://github.com/Soulter/AstrBot)
- **作者主页**: [https://github.com/muyouzhi6](https://github.com/muyouzhi6)

## 🔧 开发说明

### 技术栈
- **GUI 框架**：PySide6 (Qt6)
- **异步通信**：线程 + 队列
- **截图服务**：mss
- **音频处理**：pyaudio

### 扩展开发
1. 继承 `MessageBridge` 实现自定义消息处理
2. 在 `services/` 目录添加新的后台服务
3. 在 `gui/` 目录添加新的 UI 组件

## 📄 许可证

MIT License

## 🙏 致谢

- [AstrBot](https://github.com/Soulter/AstrBot) - 强大的 AI 聊天机器人框架
- [PySide6](https://www.qt.io/qt-for-python) - 优秀的 Python GUI 框架