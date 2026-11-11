import unittest
import sys
import json
from pathlib import Path
from types import SimpleNamespace

from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.agent_runtime import ScholarshipAgentRuntime


async def collect_events(runtime, part):
    return [event async for event in runtime._translate(part)]


class AgentEventTranslationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.runtime = ScholarshipAgentRuntime()

    async def test_translates_text_chunk(self):
        events = await collect_events(
            self.runtime,
            {"type": "messages", "data": (AIMessageChunk(content="评估结果"), {})},
        )

        self.assertEqual(events, [{"type": "token", "content": "评估结果"}])

    async def test_tool_message_is_never_emitted_as_answer_token(self):
        message = ToolMessage(
            content='{"matches":[{"content":"完整政策原文"}]}',
            tool_call_id="call-1",
            name="search_scholarship_policy",
        )
        events = await collect_events(
            self.runtime,
            {"type": "messages", "data": (message, {})},
        )

        self.assertEqual(events, [])

    async def test_translates_todos(self):
        todos = [{"content": "检索政策", "status": "in_progress"}]
        events = await collect_events(
            self.runtime,
            {"type": "updates", "data": {"model": {"todos": todos}}},
        )

        self.assertEqual(events, [{"type": "todo", "items": todos}])

    async def test_translates_tool_call(self):
        message = AIMessage(
            content="",
            tool_calls=[{"name": "search_scholarship_policy", "args": {"query": "国奖"}, "id": "call-1"}],
        )
        events = await collect_events(
            self.runtime,
            {"type": "updates", "data": {"model": {"messages": [message]}}},
        )

        self.assertEqual(events[0]["type"], "tool_call")
        self.assertEqual(events[0]["name"], "search_scholarship_policy")

    async def test_reports_length_truncation(self):
        message = AIMessage(
            content="未完成的回答",
            response_metadata={"finish_reason": "length"},
        )
        events = await collect_events(
            self.runtime,
            {"type": "updates", "data": {"model": {"messages": [message]}}},
        )

        self.assertIn({"type": "generation_truncated"}, events)

    async def test_translates_tool_result_with_bounded_preview(self):
        message = ToolMessage(content="x" * 500, tool_call_id="call-1", name="policy_search")
        events = await collect_events(
            self.runtime,
            {"type": "updates", "data": {"tools": {"messages": [message]}}},
        )

        self.assertEqual(events[0]["type"], "tool_result")
        self.assertEqual(events[0]["name"], "policy_search")
        self.assertEqual(len(events[0]["preview"]), 180)

    def test_policy_tool_preview_hides_raw_policy_text(self):
        content = json.dumps(
            {
                "matches": [
                    {"source": "政策A.pdf", "content": "很长的政策原文" * 100},
                    {"source": "政策B.pdf", "content": "另一段政策原文" * 100},
                ]
            },
            ensure_ascii=False,
        )
        preview = self.runtime._tool_result_preview("search_scholarship_policy", content)

        self.assertIn("找到 2 条相关证据", preview)
        self.assertIn("政策A.pdf", preview)
        self.assertNotIn("很长的政策原文", preview)

    async def test_translates_human_approval_interrupt(self):
        interrupt = SimpleNamespace(
            id="interrupt-1",
            value={
                "action_requests": [
                    {
                        "name": "save_application_report",
                        "args": {"report_name": "国奖评估", "markdown_content": "# 报告"},
                        "description": "保存文件需要确认",
                    }
                ],
                "review_configs": [
                    {
                        "action_name": "save_application_report",
                        "allowed_decisions": ["approve", "edit", "reject"],
                    }
                ],
            },
        )
        events = await collect_events(
            self.runtime,
            {"type": "updates", "data": {"__interrupt__": [interrupt]}},
        )

        self.assertEqual(events[0]["type"], "approval_required")
        self.assertEqual(events[0]["interrupt_id"], "interrupt-1")
        self.assertEqual(events[0]["actions"][0]["name"], "save_application_report")
        self.assertIn("reject", events[0]["actions"][0]["allowed_decisions"])


if __name__ == "__main__":
    unittest.main()
