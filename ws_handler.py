import asyncio
import base64
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set

from starlette.websockets import WebSocket, WebSocketDisconnect
from astrbot.api import logger


@dataclass
class ClientDesktopState:
    """客户端上报的桌面状态"""
    session_id: str
    timestamp: str
    active_window_title: Optional[str] = None
    active_window_process: Optional[str] = None
    active_window_pid: Optional[int] = None
    screenshot_base64: Optional[str] = None
    screenshot_width: Optional[int] = None
    screenshot_height: Optional[int] = None
    running_apps: Optional[list] = None
    window_changed: bool = False
    previous_window_title: Optional[str] = None
    received_at: Optional[datetime] = None
    
    @classmethod
    def from_dict(cls, session_id: str, data: dict) -> "ClientDesktopState":
        """从字典创建实例"""
        return cls(
            session_id=session_id,
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            active_window_title=data.get("active_window_title"),
            active_window_process=data.get("active_window_process"),
            active_window_pid=data.get("active_window_pid"),
            screenshot_base64=data.get("screenshot_base64"),
            screenshot_width=data.get("screenshot_width"),
            screenshot_height=data.get("screenshot_height"),
            running_apps=data.get("running_apps"),
            window_changed=data.get("window_changed", False),
            previous_window_title=data.get("previous_window_title"),
            received_at=datetime.now(),
        )


@dataclass
class ScreenshotRequest:
    """截图请求"""
    request_id: str
    session_id: str
    created_at: datetime = field(default_factory=datetime.now)
    timeout: float = 30.0  # 超时时间（秒）
    
    def is_expired(self) -> bool:
        """检查请求是否已超时"""
        elapsed = (datetime.now() - self.created_at).total_seconds()
        return elapsed > self.timeout


@dataclass
class ScreenshotResponse:
    """截图响应"""
    request_id: str
    session_id: str
    success: bool
    image_base64: Optional[str] = None
    image_path: Optional[str] = None
    error_message: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.now)


class ClientManager:
    """WebSocket 客户端管理器"""
    
    def __init__(self):
        # 存储活跃的连接: session_id -> WebSocket
        self.active_connections: Dict[str, WebSocket] = {}
        # 存储客户端的最新桌面状态: session_id -> ClientDesktopState
        self.client_states: Dict[str, ClientDesktopState] = {}
        # 桌面状态更新回调
        self.on_desktop_state_update: Optional[Callable[[ClientDesktopState], Any]] = None
        
        # 截图请求管理
        self._pending_screenshot_requests: Dict[str, ScreenshotRequest] = {}
        self._screenshot_futures: Dict[str, asyncio.Future] = {}
        
        # 截图保存目录
        self._screenshot_save_dir = "./temp/remote_screenshots"
        os.makedirs(self._screenshot_save_dir, exist_ok=True)
        
    async def connect(self, websocket: WebSocket, session_id: str):
        """处理新连接"""
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info(f"客户端已连接: session_id={session_id}")
        
    def disconnect(self, session_id: str):
        """处理断开连接"""
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            logger.info(f"客户端已断开: session_id={session_id}")
            
    async def send_message(self, session_id: str, message: dict):
        """发送消息给指定客户端"""
        if session_id not in self.active_connections:
            logger.warning(f"发送消息失败: 客户端未连接 session_id={session_id}")
            return
            
        websocket = self.active_connections[session_id]
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"发送消息异常: {e}")
            # 可能需要移除失效连接
            self.disconnect(session_id)
            
    async def broadcast(self, message: dict):
        """广播消息"""
        for session_id, websocket in list(self.active_connections.items()):
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"广播消息异常: session_id={session_id}, error={e}")
                self.disconnect(session_id)
                
    def update_client_state(self, session_id: str, state_data: dict):
        """更新客户端桌面状态"""
        state = ClientDesktopState.from_dict(session_id, state_data)
        self.client_states[session_id] = state
        logger.debug(f"客户端桌面状态已更新: session_id={session_id}, window={state.active_window_title}")
        return state
        
    def get_client_state(self, session_id: str) -> Optional[ClientDesktopState]:
        """获取客户端桌面状态"""
        return self.client_states.get(session_id)
        
    def get_all_client_states(self) -> Dict[str, ClientDesktopState]:
        """获取所有客户端桌面状态"""
        return self.client_states.copy()
        
    def get_active_clients_count(self) -> int:
        """获取活跃客户端数量"""
        return len(self.active_connections)
    
    def get_connected_client_ids(self) -> List[str]:
        """获取所有已连接客户端的 session_id 列表"""
        return list(self.active_connections.keys())
    
    async def request_screenshot(
        self,
        session_id: Optional[str] = None,
        timeout: float = 30.0
    ) -> ScreenshotResponse:
        """
        请求客户端截图
        
        Args:
            session_id: 目标客户端 session_id，为 None 则选择第一个可用客户端
            timeout: 超时时间（秒）
            
        Returns:
            ScreenshotResponse 对象
        """
        # 确定目标客户端
        if session_id is None:
            if not self.active_connections:
                return ScreenshotResponse(
                    request_id="",
                    session_id="",
                    success=False,
                    error_message="没有已连接的桌面客户端"
                )
            session_id = next(iter(self.active_connections.keys()))
        
        if session_id not in self.active_connections:
            return ScreenshotResponse(
                request_id="",
                session_id=session_id,
                success=False,
                error_message=f"客户端未连接: {session_id}"
            )
        
        # 创建请求
        request_id = str(uuid.uuid4())
        request = ScreenshotRequest(
            request_id=request_id,
            session_id=session_id,
            timeout=timeout
        )
        
        self._pending_screenshot_requests[request_id] = request
        
        # 创建 Future 用于等待响应
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._screenshot_futures[request_id] = future
        
        try:
            # 发送截图命令到客户端
            await self.send_message(session_id, {
                "type": "command",
                "command": "screenshot",
                "request_id": request_id,
                "params": {
                    "type": "full"  # 全屏截图
                }
            })
            
            logger.info(f"已发送截图命令到客户端: session_id={session_id}, request_id={request_id}")
            
            # 等待响应（带超时）
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
            
        except asyncio.TimeoutError:
            logger.warning(f"截图请求超时: request_id={request_id}")
            return ScreenshotResponse(
                request_id=request_id,
                session_id=session_id,
                success=False,
                error_message="截图请求超时"
            )
        except Exception as e:
            logger.error(f"截图请求失败: {e}")
            return ScreenshotResponse(
                request_id=request_id,
                session_id=session_id,
                success=False,
                error_message=str(e)
            )
        finally:
            # 清理
            self._pending_screenshot_requests.pop(request_id, None)
            self._screenshot_futures.pop(request_id, None)
    
    def handle_screenshot_response(self, session_id: str, data: dict) -> Optional[ScreenshotResponse]:
        """
        处理客户端返回的截图响应
        
        Args:
            session_id: 客户端 session_id
            data: 响应数据
            
        Returns:
            ScreenshotResponse 对象，如果无对应请求则返回 None
        """
        request_id = data.get("request_id")
        if not request_id:
            logger.warning("截图响应缺少 request_id")
            return None
        
        # 检查是否有对应的等待中的请求
        if request_id not in self._screenshot_futures:
            logger.warning(f"未找到对应的截图请求: request_id={request_id}")
            return None
        
        success = data.get("success", False)
        image_base64 = data.get("image_base64")
        error_message = data.get("error_message")
        
        response = ScreenshotResponse(
            request_id=request_id,
            session_id=session_id,
            success=success,
            image_base64=image_base64,
            error_message=error_message,
            width=data.get("width"),
            height=data.get("height")
        )
        
        # 如果成功且有图片数据，保存到文件
        if success and image_base64:
            try:
                image_data = base64.b64decode(image_base64)
                filename = f"screenshot_{request_id}_{int(time.time() * 1000)}.png"
                filepath = os.path.join(self._screenshot_save_dir, filename)
                
                with open(filepath, "wb") as f:
                    f.write(image_data)
                
                response.image_path = filepath
                logger.info(f"截图已保存: {filepath}")
            except Exception as e:
                logger.error(f"保存截图失败: {e}")
        
        # 完成 Future
        future = self._screenshot_futures.get(request_id)
        if future and not future.done():
            future.set_result(response)
        
        return response

class WebSocketHandler:
    """WebSocket 处理器"""
    
    def __init__(self, client_manager: ClientManager):
        self.manager = client_manager
        
    async def handle_websocket(self, websocket: WebSocket):
        """处理 WebSocket 连接请求"""
        # 简单的鉴权：检查 token (在 query params 中)
        # 注意：实际生产环境应使用更严格的验证，例如验证 JWT
        token = websocket.query_params.get("token")
        session_id = websocket.query_params.get("session_id")
        
        if not token or not session_id:
            logger.warning(f"WebSocket 连接拒绝: 缺少 token 或 session_id")
            await websocket.close(code=1008)
            return

        # TODO: 验证 token 有效性
        # 这里暂时信任，因为是内网/本地部署插件
        
        await self.manager.connect(websocket, session_id)
        
        try:
            while True:
                data = await websocket.receive_json()
                # 处理客户端发送的消息
                msg_type = data.get("type")
                
                if msg_type == "heartbeat":
                    await websocket.send_json({"type": "heartbeat_ack"})
                    
                elif msg_type == "desktop_state":
                    # 处理客户端桌面状态上报
                    state_data = data.get("data", {})
                    state = self.manager.update_client_state(session_id, state_data)
                    
                    # 触发回调（如果设置）
                    if self.manager.on_desktop_state_update:
                        try:
                            result = self.manager.on_desktop_state_update(state)
                            if asyncio.iscoroutine(result):
                                await result
                        except Exception as e:
                            logger.error(f"桌面状态回调执行失败: {e}")
                    
                    # 确认收到
                    await websocket.send_json({
                        "type": "desktop_state_ack",
                        "timestamp": state.timestamp,
                    })
                    
                elif msg_type == "state_sync":
                    # 处理客户端状态同步（保留向后兼容）
                    pass
                
                elif msg_type == "screenshot_response":
                    # 处理客户端截图响应
                    response_data = data.get("data", {})
                    self.manager.handle_screenshot_response(session_id, response_data)
                    logger.debug(f"收到截图响应: session_id={session_id}")
                
                elif msg_type == "command_result":
                    # 处理通用命令执行结果
                    command = data.get("command")
                    if command == "screenshot":
                        response_data = data.get("data", {})
                        self.manager.handle_screenshot_response(session_id, response_data)
                    
        except WebSocketDisconnect:
            self.manager.disconnect(session_id)
        except Exception as e:
            logger.error(f"WebSocket 错误: {e}")
            self.manager.disconnect(session_id)