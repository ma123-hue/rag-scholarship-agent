"""奖助学金领域 MCP 工具服务。

本文件以 stdio 运行。协议期间 stdout 由 MCP 占用，不要在工具中 print。
"""
from __future__ import annotations

import asyncio
import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path

import httpx
from mcp.server.fastmcp import FastMCP


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

mcp = FastMCP("scholarship-agent-tools")


def _json(data: dict | list) -> str:
    return json.dumps(data, ensure_ascii=False)


@mcp.tool()
async def search_scholarship_policy(query: str, limit: int = 3) -> str:
    """检索本校奖助学金政策原文。

    用户询问奖学金、助学金、评定条件、金额、材料或申请流程时使用。
    默认只返回最相关的 3 条精简证据。应综合归纳，不要逐条复述或粘贴原文；
    返回的 source 必须作为最终答复的证据来源，count 为 0 时不得编造。
    """
    cleaned = query.strip()
    if not cleaned:
        return _json({"ok": False, "error": "query_required", "message": "检索问题不能为空"})

    # MCP stdio 子进程使用异步 HTTP 与轻量 JSON 索引，不加载 Chroma。
    from app.core.config import get_settings

    safe_limit = max(1, min(limit, 4))
    settings = get_settings()
    settings.require_online_api_keys()
    embedding_url = f"{settings.embedding_api_base_url.rstrip('/')}/embeddings"
    async with httpx.AsyncClient(timeout=settings.llm_request_timeout) as client:
        response = await client.post(
            embedding_url,
            headers={"Authorization": f"Bearer {settings.resolved_embedding_api_key}"},
            json={"model": settings.embedding_model, "input": [cleaned]},
        )
        response.raise_for_status()
        vector = response.json()["data"][0]["embedding"]

    index_path = settings.resolved_policy_search_index
    if not index_path.exists():
        return _json(
            {
                "ok": False,
                "error": "policy_index_missing",
                "message": "政策检索索引不存在，请先运行 backend/ingest.py 重建知识库",
            }
        )
    index_data = json.loads(await asyncio.to_thread(index_path.read_text, encoding="utf-8"))
    query_norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    ranked = []
    for entry in index_data.get("entries", []):
        candidate = entry.get("embedding") or []
        if len(candidate) != len(vector):
            continue
        candidate_norm = math.sqrt(sum(value * value for value in candidate)) or 1.0
        score = sum(left * right for left, right in zip(vector, candidate, strict=True))
        ranked.append((score / (query_norm * candidate_norm), entry))
    ranked.sort(key=lambda item: item[0], reverse=True)
    matches = [
        {
            "source": Path(str(entry.get("metadata", {}).get("source", "未知来源"))).name,
            "page": entry.get("metadata", {}).get("page"),
            "content": str(entry.get("content", ""))[:800],
            "score": round(score, 6),
        }
        for score, entry in ranked[:safe_limit]
    ]
    return _json({"ok": True, "count": len(matches), "matches": matches})


PROFILE_PATTERNS = {
    "grade": r"(大[一二三四]|研[一二三])",
    "gpa": r"(?:绩点|GPA|gpa)\s*[:：]?\s*(\d+(?:\.\d+)?)",
    "rank_percent": r"(?:专业|年级|综合测评|综测)?\s*(?:排名)?\s*前\s*(\d+(?:\.\d+)?)\s*%",
    "average_score": r"(?:平均分|成绩)\s*[:：]?\s*(\d+(?:\.\d+)?)",
}


@mcp.tool()
def extract_student_profile(description: str) -> str:
    """从学生的自然语言描述中提取资格评估需要的事实。

    用户提供年级、绩点、排名、困难认定、挂科、违纪或获奖情况时使用。
    本工具只提取用户明确表达的事实，不推测、不生成政策结论。
    """
    text = description.strip()
    profile: dict[str, object] = {"raw": text}
    for field, pattern in PROFILE_PATTERNS.items():
        match = re.search(pattern, text)
        if match:
            value = match.group(1)
            profile[field] = float(value) if field != "grade" else value

    profile["financial_difficulty_recognized"] = bool(
        re.search(r"(已|通过|有).{0,6}(家庭经济困难认定|困难认定|贫困认定|贫困证明)", text)
    )
    profile["has_failed_course"] = not bool(re.search(r"(没有|无).{0,3}(挂科|不及格)", text)) if re.search(r"挂科|不及格", text) else None
    profile["has_discipline_record"] = not bool(re.search(r"(没有|无).{0,3}(违纪|处分)", text)) if re.search(r"违纪|处分", text) else None
    awards = re.findall(r"(?:获得|获)([^，。；]{2,30}(?:奖|称号|竞赛))", text)
    if awards:
        profile["awards"] = awards

    return _json({"ok": True, "profile": profile})


@mcp.tool()
def compare_profile_with_policy(student_profile_json: str, policy_requirements_json: str) -> str:
    """将学生事实与已从政策原文中提取的条件逐项比较。

    必须先调用政策检索工具，再把有证据的条件传入本工具。
    两个参数都应是 JSON 对象；本工具不会自行补造政策条件。
    """
    try:
        profile = json.loads(student_profile_json)
        requirements = json.loads(policy_requirements_json)
    except json.JSONDecodeError as exc:
        return _json({"ok": False, "error": "invalid_json", "message": str(exc)})

    if not isinstance(profile, dict) or not isinstance(requirements, dict):
        return _json({"ok": False, "error": "object_required", "message": "参数必须是 JSON 对象"})

    satisfied: list[dict] = []
    missing: list[dict] = []
    unmet: list[dict] = []
    for key, expected in requirements.items():
        if key not in profile or profile[key] is None:
            missing.append({"field": key, "required": expected})
            continue
        actual = profile[key]
        passed = actual == expected
        if isinstance(expected, dict):
            if "min" in expected:
                passed = isinstance(actual, (int, float)) and actual >= expected["min"]
            elif "max" in expected:
                passed = isinstance(actual, (int, float)) and actual <= expected["max"]
            elif "equals" in expected:
                passed = actual == expected["equals"]
        target = satisfied if passed else unmet
        target.append({"field": key, "actual": actual, "required": expected})

    status = "eligible" if not missing and not unmet else "insufficient_information" if missing else "not_eligible"
    return _json({"ok": True, "status": status, "satisfied": satisfied, "missing": missing, "unmet": unmet})


@mcp.tool()
def build_application_checklist(scholarship_name: str, missing_items_json: str = "[]") -> str:
    """整理指定奖助学金的申请材料和待补充信息清单。

    应在政策检索和资格比较之后使用。本工具只整理传入的缺失项，
    具体材料名称仍必须以检索到的政策原文为准。
    """
    try:
        missing = json.loads(missing_items_json)
    except json.JSONDecodeError as exc:
        return _json({"ok": False, "error": "invalid_json", "message": str(exc)})
    if not isinstance(missing, list):
        return _json({"ok": False, "error": "list_required", "message": "missing_items_json 必须是 JSON 数组"})
    return _json(
        {
            "ok": True,
            "scholarship": scholarship_name.strip(),
            "missing_items": missing,
            "next_steps": ["核对当年通知和截止时间", "按政策原文准备证明材料", "提交前请辅导员或资助中心复核"],
        }
    )


@mcp.tool()
def save_application_report(report_name: str, markdown_content: str) -> str:
    """将用户确认后的奖助学金评估报告保存为 Markdown 文件。

    这是有文件写入副作用的工具，必须经过人工审批后才能执行。仅当用户明确要求
    保存报告时调用。文件固定写入项目 generated_reports 目录，不能指定任意路径。
    """
    title = report_name.strip()
    content = markdown_content.strip()
    if not title:
        return _json({"ok": False, "error": "report_name_required"})
    if not content:
        return _json({"ok": False, "error": "content_required"})
    if len(content) > 50000:
        return _json({"ok": False, "error": "content_too_long", "max_length": 50000})

    from app.core.config import get_settings

    reports_dir = get_settings().resolved_generated_reports_dir
    reports_dir.mkdir(parents=True, exist_ok=True)
    safe_stem = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", title, flags=re.UNICODE).strip("-_")[:60]
    safe_stem = safe_stem or "application-report"
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    target = reports_dir / f"{safe_stem}-{timestamp}.md"
    with target.open("x", encoding="utf-8") as handle:
        handle.write(content + "\n")
    try:
        display_path = str(target.relative_to(ROOT_DIR))
    except ValueError:
        display_path = str(target)

    return _json(
        {
            "ok": True,
            "report_name": title,
            "path": display_path,
            "bytes": target.stat().st_size,
        }
    )


if __name__ == "__main__":
    mcp.run()
