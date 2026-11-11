"""运行少量真实模型用例并生成 JSON 与 Markdown 评测报告。"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from evals.scoring import markdown_report, score_case, summarize


async def observe_case(runtime: Any, case: dict[str, Any], run_id: str) -> dict[str, Any]:
    started = time.perf_counter()
    answer_parts: list[str] = []
    tools: list[str] = []
    truncated = False
    approval_required = False
    error = ""
    thread_id = f"eval-{run_id}-{case['id']}"

    try:
        for message in case["messages"]:
            async for event in runtime.stream(thread_id, message):
                event_type = event.get("type")
                if event_type == "token":
                    answer_parts.append(str(event.get("content", "")))
                elif event_type == "tool_call":
                    name = str(event.get("name", ""))
                    if name:
                        tools.append(name)
                elif event_type == "generation_truncated":
                    truncated = True
                elif event_type == "approval_required":
                    approval_required = True
    except Exception as exc:  # 评测报告需要保留单项失败，不能中断整批
        error = f"{type(exc).__name__}: {exc}"

    return {
        "answer": "".join(answer_parts).strip(),
        "tools": tools,
        "tool_call_count": len(tools),
        "duration_seconds": round(time.perf_counter() - started, 2),
        "truncated": truncated,
        "approval_required": approval_required,
        "error": error,
    }


async def run(selected_ids: set[str] | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    # 评测检查点与日常聊天隔离，避免污染用户会话或争用正在运行的服务。
    os.environ["AGENT_CHECKPOINT_DB"] = "./evals/eval_checkpoints.db"
    from app.core.config import get_settings
    from app.services.agent_runtime import ScholarshipAgentRuntime

    cases = json.loads((ROOT_DIR / "evals" / "cases.json").read_text(encoding="utf-8"))
    if selected_ids:
        cases = [case for case in cases if case["id"] in selected_ids]
    if not cases:
        raise ValueError("没有匹配的评测用例")

    runtime = ScholarshipAgentRuntime()
    settings = get_settings()
    run_id = datetime.now().strftime("%Y%m%d%H%M%S")
    results: list[dict[str, Any]] = []
    try:
        for index, case in enumerate(cases, start=1):
            print(f"[{index}/{len(cases)}] {case['name']} ...", flush=True)
            observation = await observe_case(runtime, case, run_id)
            result = score_case(case, observation)
            results.append(result)
            print(
                f"  {'PASS' if result['passed'] else 'FAIL'} "
                f"{result['duration_seconds']:.2f}s tools={result['tools']}",
                flush=True,
            )
    finally:
        await runtime.close()

    metadata = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "model": settings.llm_chat_model,
        "summary": summarize(results),
    }
    return metadata, results


def main() -> None:
    parser = argparse.ArgumentParser(description="运行奖助学金 Agent 端到端评测")
    parser.add_argument("--case", action="append", dest="cases", help="只运行指定用例 ID，可重复")
    args = parser.parse_args()
    metadata, results = asyncio.run(run(set(args.cases) if args.cases else None))

    report_dir = ROOT_DIR / "evals" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = {**metadata, "results": results}
    (report_dir / "latest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (report_dir / "latest.md").write_text(
        markdown_report(metadata, results), encoding="utf-8"
    )
    summary = metadata["summary"]
    print(
        f"完成：{summary['passed']}/{summary['total']} 通过，"
        f"通过率 {summary['pass_rate']}%，报告位于 evals/reports/latest.md"
    )
    raise SystemExit(0 if summary["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
