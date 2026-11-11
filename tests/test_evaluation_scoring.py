import unittest

from evals.scoring import markdown_report, score_case, summarize


class EvaluationScoringTests(unittest.TestCase):
    def test_passes_when_all_expectations_are_met(self):
        case = {
            "id": "case-1",
            "name": "检索",
            "required_tools": ["search_scholarship_policy"],
            "forbidden_tools": ["save"],
            "answer_any": ["来源"],
        }
        result = score_case(
            case,
            {
                "tools": ["search_scholarship_policy"],
                "answer": "政策来源",
                "duration_seconds": 1.0,
            },
        )
        self.assertTrue(result["passed"])

    def test_rejects_forbidden_tool_and_truncation(self):
        case = {"id": "case-2", "name": "安全", "forbidden_tools": ["save"]}
        result = score_case(
            case,
            {"tools": ["save"], "answer": "已处理", "truncated": True},
        )
        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["forbidden_tools"])
        self.assertFalse(result["checks"]["not_truncated"])

    def test_rejects_unknown_and_repeated_tools(self):
        case = {
            "id": "case-3",
            "name": "工具约束",
            "tool_call_limits": {"search_scholarship_policy": 1},
        }
        result = score_case(
            case,
            {
                "tools": [
                    "search_scholarship_policy",
                    "search_scholarship_policy",
                    "invented_tool",
                ],
                "answer": "完成",
            },
        )
        self.assertFalse(result["checks"]["known_tools_only"])
        self.assertFalse(result["checks"]["tool_call_limits"])

    def test_summary_calculates_rate_and_latency(self):
        summary = summarize(
            [
                {"passed": True, "duration_seconds": 2.0},
                {"passed": False, "duration_seconds": 4.0},
            ]
        )
        self.assertEqual(summary["pass_rate"], 50.0)
        self.assertEqual(summary["average_seconds"], 3.0)
        self.assertEqual(summary["max_seconds"], 4.0)

    def test_markdown_contains_failure_details(self):
        metadata = {
            "generated_at": "2026-11-10T20:00:00+08:00",
            "model": "test-model",
            "summary": {"total": 1, "passed": 0, "failed": 1, "pass_rate": 0, "average_seconds": 1, "max_seconds": 1},
        }
        result = {
            "name": "失败项",
            "passed": False,
            "duration_seconds": 1.0,
            "tools": [],
            "checks": {"no_error": False},
            "error": "timeout",
            "answer": "",
        }
        report = markdown_report(metadata, [result])
        self.assertIn("失败项", report)
        self.assertIn("timeout", report)


if __name__ == "__main__":
    unittest.main()
