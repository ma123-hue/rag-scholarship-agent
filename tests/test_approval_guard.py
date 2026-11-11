import unittest

from deepagents import create_deep_agent
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command


class ToolCallingFakeModel(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


class HumanApprovalGuardTests(unittest.IsolatedAsyncioTestCase):
    def build_agent(self, writes):
        @tool
        def save_application_report(report_name: str, markdown_content: str) -> str:
            """Persist a report for the approval test."""
            writes.append((report_name, markdown_content))
            return "saved"

        model = ToolCallingFakeModel(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "save_application_report",
                            "args": {"report_name": "test", "markdown_content": "body"},
                            "id": "write-1",
                        }
                    ],
                ),
                AIMessage(content="处理完成"),
            ]
        )
        return create_deep_agent(
            model=model,
            tools=[save_application_report],
            checkpointer=InMemorySaver(),
            interrupt_on={
                "save_application_report": {
                    "allowed_decisions": ["approve", "edit", "reject"],
                }
            },
        )

    async def test_reject_does_not_execute_write_tool(self):
        writes = []
        agent = self.build_agent(writes)
        config = {"configurable": {"thread_id": "reject-test"}}

        first = await agent.ainvoke({"messages": [{"role": "user", "content": "保存报告"}]}, config)
        self.assertIn("__interrupt__", first)
        await agent.ainvoke(
            Command(resume={"decisions": [{"type": "reject", "message": "不要写文件"}]}),
            config,
        )

        self.assertEqual(writes, [])

    async def test_approve_executes_write_tool_once(self):
        writes = []
        agent = self.build_agent(writes)
        config = {"configurable": {"thread_id": "approve-test"}}

        await agent.ainvoke({"messages": [{"role": "user", "content": "保存报告"}]}, config)
        await agent.ainvoke(Command(resume={"decisions": [{"type": "approve"}]}), config)

        self.assertEqual(writes, [("test", "body")])


if __name__ == "__main__":
    unittest.main()
