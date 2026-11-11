"""不依赖模型的评测判分与报告格式化。"""
from __future__ import annotations

from typing import Any


ALLOWED_TOOLS = {
    "write_todos",
    "search_scholarship_policy",
    "extract_student_profile",
    "compare_profile_with_policy",
    "build_application_checklist",
    "save_application_report",
}


def score_case(case: dict[str, Any], observation: dict[str, Any]) -> dict[str, Any]:
    tools = observation.get("tools", [])
    answer = str(observation.get("answer", ""))
    required = case.get("required_tools", [])
    forbidden = case.get("forbidden_tools", [])
    keywords = case.get("answer_any", [])
    limits = case.get("tool_call_limits", {})

    checks = {
        "required_tools": all(name in tools for name in required),
        "forbidden_tools": all(name not in tools for name in forbidden),
        "known_tools_only": all(name in ALLOWED_TOOLS for name in tools),
        "tool_call_limits": all(tools.count(name) <= limit for name, limit in limits.items()),
        "answer_keyword": not keywords or any(word in answer for word in keywords),
        "non_empty_answer": bool(answer.strip()),
        "not_truncated": not observation.get("truncated", False),
        "no_error": not observation.get("error"),
        "no_unexpected_approval": not observation.get("approval_required", False),
    }
    return {
        **observation,
        "id": case["id"],
        "name": case["name"],
        "checks": checks,
        "passed": all(checks.values()),
    }


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    passed = sum(1 for item in results if item.get("passed"))
    durations = [float(item.get("duration_seconds", 0)) for item in results]
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed / total * 100, 1) if total else 0.0,
        "average_seconds": round(sum(durations) / total, 2) if total else 0.0,
        "max_seconds": round(max(durations), 2) if durations else 0.0,
    }


def markdown_report(metadata: dict[str, Any], results: list[dict[str, Any]]) -> str:
    summary = metadata["summary"]
    lines = [
        "# Agent 端到端评测报告",
        "",
        f"- 执行时间：{metadata['generated_at']}",
        f"- 聊天模型：{metadata['model']}",
        f"- 用例总数：{summary['total']}",
        f"- 通过：{summary['passed']}",
        f"- 失败：{summary['failed']}",
        f"- 通过率：{summary['pass_rate']}%",
        f"- 平均耗时：{summary['average_seconds']} 秒",
        f"- 最长耗时：{summary['max_seconds']} 秒",
        "",
        "| 用例 | 结果 | 耗时 | 工具调用 | 失败检查 |",
        "|---|---:|---:|---|---|",
    ]
    for item in results:
        failed_checks = [name for name, ok in item["checks"].items() if not ok]
        tool_text = "、".join(item.get("tools", [])) or "无"
        lines.append(
            f"| {item['name']} | {'通过' if item['passed'] else '失败'} | "
            f"{item.get('duration_seconds', 0):.2f}s | {tool_text} | "
            f"{'、'.join(failed_checks) or '-'} |"
        )
    lines.extend(["", "## 失败用例详情", ""])
    failures = [item for item in results if not item["passed"]]
    if not failures:
        lines.append("无。")
    for item in failures:
        lines.extend(
            [
                f"### {item['name']}",
                "",
                f"- 失败检查：{'、'.join(name for name, ok in item['checks'].items() if not ok)}",
                f"- 错误：{item.get('error') or '无'}",
                f"- 回答摘要：{str(item.get('answer', ''))[:300]}",
                "",
            ]
        )
    lines.extend(
        [
            "## 判分说明",
            "",
            "每项用例检查预期工具、禁止工具、回答关键字、空回答、长度截断、运行错误和意外审批。",
            "线上模型具有少量随机性，正式答辩数据建议连续运行三轮并报告平均通过率。",
            "",
        ]
    )
    return "\n".join(lines)
