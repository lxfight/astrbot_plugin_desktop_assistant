# 🖥️ AstrBot 桌面助手服务端插件 (Server Plugin)

[![AstrBot](https://img.shields.io/badge/AstrBot-v3.0%2B-purple)](https://github.com/Soulter/AstrBot)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

本插件是 [AstrBot 桌面助手客户端](https://github.com/muyouzhi6/Astrbot-desktop-assistant) 的服务端适配器，负责处理客户端连接、消息路由及多模态数据交互。

> ⚠️ **注意**：本项目仅为服务端插件，需配合桌面客户端使用。

## ✨ 核心功能

### 🔌 API 适配与桥接
- **协议转换**：将 AstrBot 内部消息转换为客户端可识别的格式。
- **即时通讯**：基于 HTTP/WebSocket 实现低延迟的双向通信。

### 🖥️ 桌面环境感知
- **屏幕监控**：接收并处理客户端上传的屏幕截图，为视觉模型提供输入。
- **主动交互**：支持基于屏幕内容的主动对话与建议（需配置）。

### 🛠️ 扩展能力
- **鉴权管理**：管理客户端的连接认证与权限。
- **资源代理**：处理语音、图片等媒体资源的转发与存储。

## 📦 安装说明

### 方式 1：插件市场安装
在 AstrBot 管理面板的插件市场中搜索 `desktop_assistant` 并安装。

### 方式 2：手动安装
将本项目克隆至 AstrBot 的插件目录：
```bash
cd data/plugins
git clone https://github.com/muyouzhi6/astrbot_plugin_desktop_assistant.git
pip install -r astrbot_plugin_desktop_assistant/requirements.txt
```

## ⚙️ 配置说明
安装后重启 AstrBot，在插件配置页面可调整以下参数：
- **服务端口**：API 监听端口。
- **主动对话**：开启/关闭基于屏幕内容的主动交互功能。
- **监控间隔**：设置屏幕分析的时间间隔。

## ✨bug反馈及改进
QQ群：1037856742
诚挚欢迎广大开发者提出宝贵的意见以及优化代码

## 📄 许可证

本项目采用 MIT 许可证。
