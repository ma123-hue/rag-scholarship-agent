import tempfile
import unittest
from pathlib import Path

import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from typing_extensions import TypedDict


class ApprovalState(TypedDict, total=False):
    result: str


def approval_node(_: ApprovalState) -> ApprovalState:
    decision = interrupt({"operation": "write_report"})
    return {"result": str(decision)}


class PersistentCheckpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_interrupt_can_resume_after_database_reopen(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "checkpoints.db"
            config = {"configurable": {"thread_id": "recovery-test"}}

            connection = await aiosqlite.connect(database_path)
            saver = AsyncSqliteSaver(connection)
            await saver.setup()
            graph_builder = StateGraph(ApprovalState)
            graph_builder.add_node("approval", approval_node)
            graph_builder.add_edge(START, "approval")
            graph_builder.add_edge("approval", END)
            graph = graph_builder.compile(checkpointer=saver)

            first_result = await graph.ainvoke({}, config)
            self.assertIn("__interrupt__", first_result)
            await connection.close()

            reopened_connection = await aiosqlite.connect(database_path)
            reopened_saver = AsyncSqliteSaver(reopened_connection)
            await reopened_saver.setup()
            reopened_graph = graph_builder.compile(checkpointer=reopened_saver)
            resumed_result = await reopened_graph.ainvoke(Command(resume="approved"), config)
            await reopened_connection.close()

            self.assertEqual(resumed_result["result"], "approved")


if __name__ == "__main__":
    unittest.main()
