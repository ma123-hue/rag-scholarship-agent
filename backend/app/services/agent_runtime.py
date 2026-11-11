"""DeepAgent 运行时与前端事件投影。"""
from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import AsyncIterator
from typing import Any

import aiosqlite
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command

from app.core.config import get_settings


SYSTEM_PROMPT = """
你是“高校奖助学金申请评估智能体”。你不只回答问题，还要自主规划并调用工具完成任务。

必须遵守：
1. 需要三步及以上的任务，先使用 write_todos 列出计划，完成一步就更新状态。
2. 涉及申请条件、金额、材料、流程或截止时间时，必须先调用 search_scholarship_policy；同一个用户问题默认只调用一次，只有首次检索失败或用户明确要求扩大范围时才能再次调用。
3. 只能根据工具返回的政策证据下结论；无命中时明确说明证据不足，不得编造。
4. 资格评估必须区分：已满足、不满足、信息缺失，不得把“缺失”当成“不满足”。
5. 默认使用“简洁回答”：先直接给结论，再列最多 3 个要点；除非用户明确要求详细分析、逐条对比或生成报告，否则全文控制在 200～300 个中文字符。
6. 必须综合归纳检索证据，禁止按检索结果逐篇复述、粘贴政策原文或展示检索分数。来源放在末尾一行，只列 1～3 个文件名。
7. 用户明确要求详细回答时也要去重，只展开与问题直接相关的条款。
8. 最终提醒用户以当年官方通知为准，但不要反复重复免责声明。
9. 只有用户明确要求保存报告时才能调用 save_application_report；该工具执行前必须等待人工审批。
10. 不要谎称已经删除或提交任何东西；报告只有在工具返回 ok=true 后才算保存成功。
11. 可用的业务工具只有 search_scholarship_policy、extract_student_profile、compare_profile_with_policy、build_application_checklist、save_application_report；不得编造或尝试调用其他工具名。
12. 即使奖项名称疑似虚构或用户要求跳过检索，只要回答涉及政策是否存在、是否有依据，就必须实际调用 search_scholarship_policy；没有调用时禁止声称“已检索”“未检索到”或直接断言政策不存在。
13. 同一轮中每个业务工具默认最多调用一次。只有工具明确返回 ok=false、参数校验失败，或用户明确要求扩大检索时才允许重试；不要用相同或近似参数重复调用。
""".strip()


class ApprovalNotPendingError(RuntimeError):
    """当前会话没有可恢复的审批中断。"""


class ScholarshipAgentRuntime:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._agent: Any | None = None
        self._init_lock = asyncio.Lock()
        self._checkpoint_connection: aiosqlite.Connection | None = None
        self._thread_locks: dict[str, asyncio.Lock] = {}

    def _thread_lock(self, thread_id: str) -> asyncio.Lock:
        return self._thread_locks.setdefault(thread_id, asyncio.Lock())

    async def _build(self) -> Any:
        if self._agent is not None:
            return self._agent
        async with self._init_lock:
            if self._agent is not None:
                return self._agent

            from deepagents import create_deep_agent
            from langchain_mcp_adapters.client import MultiServerMCPClient

            client = MultiServerMCPClient(
                {
                    "scholarship": {
                        "transport": self.settings.mcp_transport,
                        "command": sys.executable,
                        "args": [str(self.settings.scholarship_mcp_script)],
                    }
                }
            )
            tools = await client.get_tools()
            self.settings.resolved_agent_checkpoint_db.parent.mkdir(parents=True, exist_ok=True)
            self._checkpoint_connection = await aiosqlite.connect(self.settings.resolved_agent_checkpoint_db)
            checkpointer = AsyncSqliteSaver(self._checkpoint_connection)
            await checkpointer.setup()
            self.settings.require_online_api_keys()
            model = ChatOpenAI(
                model=self.settings.llm_chat_model,
                base_url=self.settings.llm_api_base_url,
                api_key=self.settings.llm_api_key,
                temperature=0.1,
                timeout=self.settings.llm_request_timeout,
                max_retries=self.settings.llm_max_retries,
                max_completion_tokens=self.settings.llm_max_output_tokens,
                stream_chunk_timeout=30,
                extra_body={"enable_thinking": self.settings.llm_enable_thinking},
            )
            self._agent = create_deep_agent(
                model=model,
                tools=tools,
                system_prompt=SYSTEM_PROMPT,
                checkpointer=checkpointer,
                interrupt_on={
                    "save_application_report": {
                        "allowed_decisions": ["approve", "edit", "reject"],
                        "description": "保存申请评估报告会在项目目录中创建文件，需要你确认。",
                    }
                },
            )
            return self._agent

    async def stream(self, thread_id: str, message: str) -> AsyncIterator[dict[str, Any]]:
        async with self._thread_lock(thread_id):
            if await self.pending_approval(thread_id):
                raise RuntimeError("当前会话有待处理审批，请先批准、修改或拒绝后再发送新消息")
            async for event in self._stream_input(
                thread_id,
                {"messages": [{"role": "user", "content": message}]},
            ):
                yield event

    async def resume(
        self,
        thread_id: str,
        decisions: list[dict[str, Any]],
    ) -> AsyncIterator[dict[str, Any]]:
        async with self._thread_lock(thread_id):
            approval = await self.pending_approval(thread_id)
            if not approval:
                raise ApprovalNotPendingError("当前会话没有待审批操作，可能已经处理或失效")
            actions = approval.get("actions", [])
            if len(decisions) != len(actions):
                raise ValueError("审批决定数量必须与待审批操作数量一致")

            normalized: list[dict[str, Any]] = []
            for decision, action in zip(decisions, actions, strict=True):
                kind = decision.get("type")
                if kind == "approve":
                    normalized.append({"type": "approve"})
                elif kind == "reject":
                    normalized.append(
                        {"type": "reject", "message": decision.get("message") or "用户拒绝执行该操作"}
                    )
                elif kind == "edit":
                    edited_args = decision.get("edited_args")
                    if not isinstance(edited_args, dict):
                        raise ValueError("修改操作必须提供 edited_args 对象")
                    normalized.append(
                        {
                            "type": "edit",
                            "edited_action": {"name": action.get("name"), "args": edited_args},
                        }
                    )
                else:
                    raise ValueError(f"不支持的审批决定：{kind}")

            async for event in self._stream_input(
                thread_id,
                Command(resume={"decisions": normalized}),
            ):
                yield event

    def _config(self, thread_id: str) -> dict[str, Any]:
        return {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": self.settings.agent_max_steps * 2 + 4,
        }

    async def _stream_input(self, thread_id: str, agent_input: Any) -> AsyncIterator[dict[str, Any]]:
        agent = await self._build()
        stream = agent.astream(
            agent_input,
            config=self._config(thread_id),
            stream_mode=["messages", "updates"],
            version="v2",
        )
        async for part in stream:
            async for event in self._translate(part):
                yield event

    async def pending_approval(self, thread_id: str) -> dict[str, Any] | None:
        agent = await self._build()
        snapshot = await agent.aget_state(self._config(thread_id))
        interrupts = getattr(snapshot, "interrupts", ()) or ()
        if not interrupts:
            return None
        return self._approval_event(interrupts[0])

    async def close(self) -> None:
        if self._checkpoint_connection is not None:
            await self._checkpoint_connection.close()
            self._checkpoint_connection = None
            self._agent = None

    @staticmethod
    def _approval_event(interrupt: Any) -> dict[str, Any]:
        value = getattr(interrupt, "value", interrupt)
        interrupt_id = getattr(interrupt, "id", "")
        if not isinstance(value, dict):
            value = {"description": str(value)}
        action_requests = value.get("action_requests") or []
        review_configs = value.get("review_configs") or []
        actions = []
        for index, action in enumerate(action_requests):
            review = review_configs[index] if index < len(review_configs) else {}
            actions.append(
                {
                    "name": action.get("name", ""),
                    "args": action.get("args", {}),
                    "description": action.get("description", value.get("description", "")),
                    "allowed_decisions": review.get(
                        "allowed_decisions", ["approve", "edit", "reject"]
                    ),
                }
            )
        return {
            "type": "approval_required",
            "interrupt_id": interrupt_id,
            "actions": actions,
        }

    async def _translate(self, part: Any) -> AsyncIterator[dict[str, Any]]:
        if isinstance(part, dict) and "type" in part:
            kind = part.get("type")
            data = part.get("data")
        elif isinstance(part, tuple) and len(part) == 2:
            kind, data = part
        else:
            return

        if kind == "messages":
            chunk = data[0] if isinstance(data, (tuple, list)) and data else data
            # messages 流同时包含 AIMessage、ToolMessage 等。ToolMessage 中是完整的
            # 检索 JSON，绝不能作为回答 token 推给前端。
            if not isinstance(chunk, (AIMessage, AIMessageChunk)):
                return
            text = getattr(chunk, "text", "") or getattr(chunk, "content", "") or ""
            if isinstance(text, str) and text:
                yield {"type": "token", "content": text}
            return

        if kind != "updates" or not isinstance(data, dict):
            return

        interrupts = data.get("__interrupt__") or ()
        for interrupt in interrupts:
            yield self._approval_event(interrupt)

        for node_name, update in data.items():
            if node_name == "__interrupt__":
                continue
            if not isinstance(update, dict):
                continue
            todos = update.get("todos")
            if isinstance(todos, list):
                yield {"type": "todo", "items": todos}
            for msg in update.get("messages", []) or []:
                calls = getattr(msg, "tool_calls", None) or []
                for call in calls:
                    yield {
                        "type": "tool_call",
                        "name": call.get("name", ""),
                        "args": call.get("args", {}),
                    }
                if msg.__class__.__name__ == "ToolMessage":
                    raw_content = str(getattr(msg, "content", ""))
                    yield {
                        "type": "tool_result",
                        "name": getattr(msg, "name", "") or "",
                        "preview": self._tool_result_preview(
                            getattr(msg, "name", "") or "",
                            raw_content,
                        ),
                    }
                if (
                    isinstance(msg, AIMessage)
                    and getattr(msg, "response_metadata", {}).get("finish_reason") == "length"
                ):
                    yield {"type": "generation_truncated"}

    @staticmethod
    def _tool_result_preview(tool_name: str, content: str) -> str:
        """执行轨迹只显示摘要，避免把政策原文再次输出到界面。"""
        if tool_name == "search_scholarship_policy":
            try:
                payload = json.loads(content)
                matches = payload.get("matches", []) if isinstance(payload, dict) else []
                sources: list[str] = []
                for match in matches:
                    source = str(match.get("source", "未知来源"))
                    if source not in sources:
                        sources.append(source)
                suffix = f"；来源：{'、'.join(sources[:3])}" if sources else ""
                return f"检索完成，共找到 {len(matches)} 条相关证据{suffix}"
            except (json.JSONDecodeError, TypeError, AttributeError):
                return "政策检索已完成"
        return content[:180]


_runtime = ScholarshipAgentRuntime()


def get_agent_runtime() -> ScholarshipAgentRuntime:
    return _runtime
