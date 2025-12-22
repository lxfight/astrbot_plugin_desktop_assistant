"""
数据模型模块

定义消息、事件等数据结构。
"""

from dataclasses import dataclass, field
from typing import Optional, Any, Dict, List
from datetime import datetime
from enum import Enum


class MessageType(Enum):
    """消息类型"""
    TEXT = "text"
    IMAGE = "image"
    VOICE = "voice"
    FILE = "file"
    SCREENSHOT = "screenshot"
    SYSTEM = "system"


class MessageDirection(Enum):
    """消息方向"""
    INCOMING = "incoming"  # 用户发送
    OUTGOING = "outgoing"  # AI 回复


@dataclass
class InputMessage:
    """
    输入消息
    
    从 GUI 线程发送到适配器线程的消息。
    """
    msg_type: str
    content: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "msg_type": self.msg_type,
            "content": self.content,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class OutputMessage:
    """
    输出消息
    
    从适配器线程发送到 GUI 线程的消息。
    """
    msg_type: str
    content: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    streaming: bool = False
    finished: bool = False
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "msg_type": self.msg_type,
            "content": self.content,
            "metadata": self.metadata,
            "streaming": self.streaming,
            "finished": self.finished,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class ChatMessage:
    """
    对话消息
    
    用于 GUI 显示的消息格式。
    """
    id: str
    msg_type: MessageType
    content: Any
    direction: MessageDirection
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_user(self) -> bool:
        """是否是用户消息"""
        return self.direction == MessageDirection.INCOMING


@dataclass
class DesktopEvent:
    """
    桌面事件
    
    桌面监控产生的事件。
    """
    event_type: str
    screenshot_path: Optional[str] = None
    active_window: Optional[str] = None
    window_title: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProactiveDialogRequest:
    """
    主动对话请求
    
    AI 发起的主动对话。
    """
    trigger_reason: str
    desktop_state: Optional[DesktopEvent] = None
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


__all__ = [
    "MessageType",
    "MessageDirection",
    "InputMessage",
    "OutputMessage",
    "ChatMessage",
    "DesktopEvent",
    "ProactiveDialogRequest",
]