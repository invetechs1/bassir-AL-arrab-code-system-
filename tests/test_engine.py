import unittest

from app.engine.assessment import evaluate
from app.engine.design_assistant import suggest
from app.engine.permit_readiness import CHECKLIST, score
from app.engine.rules_store import list_rules

FULL_PARAMS = {
    "land_use": "residential",
    "plot_area_m2": 450,
    "floors": 2,
    "building_height_m": 9.5,
    "setback_front_m": 4,
    "setback_side_m": 2.5,
    "setback_rear_m": 2.5,
    "coverage_ratio": 0.55,
    "far": 1.2,
    "units": 1,
    "parking_spaces": 2,
}


class TestRulesStore(unittest.TestCase):
    def test_rules_load_and_none_are_official(self):
        rules = list_rules()
        self.assertGreaterEqual(len(rules), 8)
        for rule in rules:
            self.assertFalse(rule["is_official"], f"{rule['code']} must not be official")
            self.assertFalse(rule["is_active"], f"{rule['code']} must not be active")
            self.assertIn("governance", rule)
            self.assertIn("source_reference", rule["governance"])


class TestAssessment(unittest.TestCase):
    def test_compliant_project_passes(self):
        result = evaluate(FULL_PARAMS)
        self.assertEqual(result["overall_status"], "preliminary_pass")
        self.assertEqual(result["counts"]["fail"], 0)
        self.assertEqual(result["score"], 100.0)
        self.assertFalse(result["official_basis"])
        self.assertIn("disclaimer", result)
        self.assertIn("ar", result["disclaimer"])

    def test_violations_are_flagged(self):
        params = dict(FULL_PARAMS, setback_front_m=1.0, floors=10)
        result = evaluate(params)
        self.assertEqual(result["overall_status"], "issues_found")
        failed = {f["rule_code"] for f in result["findings"] if f["status"] == "fail"}
        self.assertIn("PRELIM-SETBACK-FRONT", failed)
        self.assertIn("PRELIM-MAX-FLOORS", failed)
        self.assertLess(result["score"], 100.0)

    def test_missing_input_needs_review(self):
        result = evaluate({"plot_area_m2": 400})
        self.assertEqual(result["overall_status"], "incomplete_input")
        self.assertGreater(result["counts"]["needs_review"], 0)

    def test_score_bounds(self):
        result = evaluate(FULL_PARAMS)
        self.assertGreaterEqual(result["score"], 0.0)
        self.assertLessEqual(result["score"], 100.0)


class TestPermitReadiness(unittest.TestCase):
    def test_all_documents_full_score(self):
        docs = {item["key"]: True for item in CHECKLIST}
        result = score(docs)
        self.assertEqual(result["readiness_score"], 100.0)
        self.assertEqual(result["readiness_level"], "ready_for_submission_review")
        self.assertEqual(result["missing"], [])

    def test_no_documents_early_stage(self):
        result = score({})
        self.assertEqual(result["readiness_score"], 0.0)
        self.assertEqual(result["readiness_level"], "early_stage")
        self.assertEqual(len(result["missing"]), len(CHECKLIST))
        self.assertIn("disclaimer", result)


class TestDesignAssistant(unittest.TestCase):
    def test_suggestions_with_plot(self):
        result = suggest({"plot_area_m2": 500, "floors": 2, "coverage_ratio": 0.5})
        self.assertTrue(result["advisory_only"])
        self.assertIn("indicative_footprint_m2", result["estimates"])
        self.assertGreater(len(result["suggestions"]), 0)

    def test_suggestions_without_plot(self):
        result = suggest({})
        self.assertEqual(result["estimates"], {})
        self.assertIn("disclaimer", result)


if __name__ == "__main__":
    unittest.main()
