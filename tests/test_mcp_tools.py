import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mcp_servers.scholarship_server import (
    build_application_checklist,
    compare_profile_with_policy,
    extract_student_profile,
    save_application_report,
)
from mcp_servers import scholarship_server


class StudentProfileToolTests(unittest.TestCase):
    def test_extracts_explicit_profile_fields(self):
        result = json.loads(
            extract_student_profile(
                "我是大二，绩点3.82，专业排名前5%，平均分89，已通过家庭经济困难认定，没有挂科，无违纪。"
            )
        )
        profile = result["profile"]

        self.assertEqual(profile["grade"], "大二")
        self.assertEqual(profile["gpa"], 3.82)
        self.assertEqual(profile["rank_percent"], 5.0)
        self.assertEqual(profile["average_score"], 89.0)
        self.assertTrue(profile["financial_difficulty_recognized"])
        self.assertFalse(profile["has_failed_course"])
        self.assertFalse(profile["has_discipline_record"])

    def test_unknown_negative_fields_remain_none(self):
        profile = json.loads(extract_student_profile("我是大一，绩点3.5。"))["profile"]

        self.assertIsNone(profile["has_failed_course"])
        self.assertIsNone(profile["has_discipline_record"])


class PolicyComparisonToolTests(unittest.TestCase):
    def test_eligible_when_every_requirement_is_satisfied(self):
        result = json.loads(
            compare_profile_with_policy(
                json.dumps({"gpa": 3.8, "rank_percent": 5, "has_failed_course": False}),
                json.dumps({"gpa": {"min": 3.5}, "rank_percent": {"max": 10}, "has_failed_course": False}),
            )
        )

        self.assertEqual(result["status"], "eligible")
        self.assertEqual(len(result["satisfied"]), 3)

    def test_missing_information_is_not_treated_as_failure(self):
        result = json.loads(
            compare_profile_with_policy(
                json.dumps({"gpa": 3.8}),
                json.dumps({"gpa": {"min": 3.5}, "rank_percent": {"max": 10}}),
            )
        )

        self.assertEqual(result["status"], "insufficient_information")
        self.assertEqual(result["missing"][0]["field"], "rank_percent")
        self.assertEqual(result["unmet"], [])

    def test_not_eligible_when_known_value_fails(self):
        result = json.loads(
            compare_profile_with_policy(
                json.dumps({"rank_percent": 25}),
                json.dumps({"rank_percent": {"max": 10}}),
            )
        )

        self.assertEqual(result["status"], "not_eligible")
        self.assertEqual(result["unmet"][0]["actual"], 25)

    def test_invalid_json_returns_structured_error(self):
        result = json.loads(compare_profile_with_policy("not-json", "{}"))

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "invalid_json")


class ChecklistToolTests(unittest.TestCase):
    def test_checklist_preserves_missing_items(self):
        result = json.loads(build_application_checklist("国家励志奖学金", '["困难认定", "成绩单"]'))

        self.assertEqual(result["scholarship"], "国家励志奖学金")
        self.assertEqual(result["missing_items"], ["困难认定", "成绩单"])
        self.assertEqual(len(result["next_steps"]), 3)

    def test_checklist_rejects_non_list_input(self):
        result = json.loads(build_application_checklist("国家奖学金", "{}"))

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "list_required")


class SaveReportToolTests(unittest.TestCase):
    def test_report_is_written_only_inside_configured_directory(self):
        with tempfile.TemporaryDirectory(dir=scholarship_server.ROOT_DIR) as temp_dir:
            reports_dir = Path(temp_dir) / "reports"
            settings = SimpleNamespace(resolved_generated_reports_dir=reports_dir)
            with patch("app.core.config.get_settings", return_value=settings):
                result = json.loads(save_application_report("../../国家奖学金/评估", "# 已确认报告"))

            self.assertTrue(result["ok"])
            files = list(reports_dir.glob("*.md"))
            self.assertEqual(len(files), 1)
            self.assertEqual(files[0].parent.resolve(), reports_dir.resolve())
            self.assertEqual(files[0].read_text(encoding="utf-8"), "# 已确认报告\n")

    def test_empty_report_is_rejected_without_creating_file(self):
        with tempfile.TemporaryDirectory(dir=scholarship_server.ROOT_DIR) as temp_dir:
            reports_dir = Path(temp_dir) / "reports"
            settings = SimpleNamespace(resolved_generated_reports_dir=reports_dir)
            with patch("app.core.config.get_settings", return_value=settings):
                result = json.loads(save_application_report("报告", "   "))

            self.assertFalse(result["ok"])
            self.assertFalse(reports_dir.exists())


if __name__ == "__main__":
    unittest.main()
