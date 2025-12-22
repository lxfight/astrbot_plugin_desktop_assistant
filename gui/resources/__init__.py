"""
资源模块

包含图标、样式表、默认头像等资源。
"""

import os

# 资源目录路径
RESOURCES_DIR = os.path.dirname(os.path.abspath(__file__))

# 资源文件路径
DEFAULT_AVATAR = os.path.join(RESOURCES_DIR, "default_avatar.png")
STYLESHEET = os.path.join(RESOURCES_DIR, "styles.qss")


def get_resource_path(filename: str) -> str:
    """获取资源文件路径"""
    return os.path.join(RESOURCES_DIR, filename)


def get_stylesheet() -> str:
    """获取样式表内容"""
    try:
        with open(STYLESHEET, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""