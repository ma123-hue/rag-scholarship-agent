from typing import Sequence

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.chat import Message

# 实现基于数据库的聊天记录管理
class DatabaseChatMessageHistory(BaseChatMessageHistory):
    # 初始化
    def __init__(self, session_id: int, window_size: int = 10):
        self.session_id = session_id
        self.window_size = window_size

    # 读取消息
    @property
    def messages(self) -> list[BaseMessage]:
        with SessionLocal() as db:
            # 构建查询：筛选当前会话ID + 按时间戳/ID倒序（最新的在前） + 限制窗口大小
            stmt = (
                select(Message)
                .where(Message.session_id == self.session_id)
                .order_by(Message.timestamp.desc(), Message.id.desc())
                .limit(self.window_size)
            )
            # 执行查询并反转结果（恢复正序：最早的在前）
            rows = list(reversed(db.execute(stmt).scalars().all()))
            output: list[BaseMessage] = []
            # 数据库记录转换为LangChain消息对象
            for row in rows:
                if row.role == "user":
                    output.append(HumanMessage(content=row.content))
                else:
                    output.append(AIMessage(content=row.content))
            return output

    # 新增消息
    def add_messages(self, messages: Sequence[BaseMessage]) -> None:
        role_map = {"human": "user", "ai": "assistant"}   # LangChain类型 -> 数据库role字段映射
        with SessionLocal() as db:
            for message in messages:
                # 构建Message模型对象并添加到会话
                db.add(
                    Message(
                        session_id=self.session_id,
                        role=role_map.get(message.type, message.type),
                        content=str(message.content),
                    )
                )
            db.commit()    # 批量提交

    # 清空消息
    def clear(self) -> None:
        with SessionLocal() as db:
            db.query(Message).filter(Message.session_id == self.session_id).delete()
            db.commit()
