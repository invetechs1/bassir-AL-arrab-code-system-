import unittest

try:
    from fastapi.testclient import TestClient

    from app.main import app

    HAS_FASTAPI = True
except ImportError:  # pragma: no cover
    HAS_FASTAPI = False

PDF_BYTES = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n%%EOF"


@unittest.skipUnless(HAS_FASTAPI, "fastapi not installed")
class TestApiEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.db.base import init_db

        init_db()
        cls.client = TestClient(app)

    def test_health(self):
        response = self.client.get("/v1/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_version(self):
        response = self.client.get("/v1/version")
        self.assertEqual(response.status_code, 200)
        self.assertIn("version", response.json())

    def test_security_headers_present(self):
        response = self.client.get("/v1/health")
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(response.headers.get("X-Frame-Options"), "DENY")
        self.assertIn("Content-Security-Policy", response.headers)

    def test_assess(self):
        response = self.client.post("/v1/assess", json={
            "land_use": "residential", "plot_area_m2": 450, "floors": 2,
            "building_height_m": 9.5, "setback_front_m": 4, "setback_side_m": 2.5,
            "setback_rear_m": 2.5, "coverage_ratio": 0.55, "far": 1.2,
            "units": 1, "parking_spaces": 2,
        })
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["overall_status"], "preliminary_pass")
        self.assertIn("disclaimer", body)
        self.assertIn("assessment_id", body)

    def test_assess_file_accepts_pdf(self):
        response = self.client.post(
            "/v1/assess/file",
            files={"file": ("plan.pdf", PDF_BYTES, "application/pdf")},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["file"]["detected_type"], "pdf")

    def test_assess_file_rejects_fake_pdf(self):
        response = self.client.post(
            "/v1/assess/file",
            files={"file": ("fake.pdf", b"MZ not a pdf", "application/pdf")},
        )
        self.assertEqual(response.status_code, 422)

    def test_assess_vision(self):
        response = self.client.post(
            "/v1/assess/vision",
            files={"file": ("plan.pdf", PDF_BYTES, "application/pdf")},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["kind"], "vision_foundation")

    def test_assistant_suggest(self):
        response = self.client.post("/v1/assistant/suggest", json={"question": "كم الارتداد الأمامي المطلوب؟"})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("relevant_sources", body)
        self.assertIn("disclaimer", body)

    def test_design_suggest(self):
        response = self.client.post("/v1/design/suggest", json={"plot_area_m2": 500, "floors": 2})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["advisory_only"])

    def test_permit_readiness(self):
        response = self.client.post("/v1/permit/readiness", json={"documents": {"title_deed": True}})
        self.assertEqual(response.status_code, 200)
        self.assertIn("readiness_score", response.json())

    def test_bim_review(self):
        response = self.client.post("/v1/bim/review", json={"model_info": {"schema": "IFC4", "storeys": 2}})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["kind"], "bim_review")

    def test_report_generate(self):
        assessment = self.client.post("/v1/assess", json={"plot_area_m2": 450}).json()
        response = self.client.post("/v1/report/generate", json={
            "title": "تقرير اختبار", "project": {"name": "Test"}, "assessment": assessment,
        })
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("report_id", body)
        self.assertFalse(body["official_basis"])

    def test_rules(self):
        response = self.client.get("/v1/rules")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["official_count"], 0)

    def test_regulatory_resources(self):
        response = self.client.get("/v1/regulatory-resources")
        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.json()["resources"]), 0)

    def test_regulatory_resources_summary(self):
        response = self.client.get("/v1/regulatory-resources/summary")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["catalog_problems"], [])

    def test_rule_candidates_from_resources(self):
        response = self.client.get("/v1/rule-candidates/from-resources")
        self.assertEqual(response.status_code, 200)
        self.assertGreater(response.json()["count"], 0)

    def test_rule_candidates_review_package(self):
        # demo principal is engineer — review requires reviewer/admin role
        response = self.client.get("/v1/rule-candidates/review-package")
        self.assertEqual(response.status_code, 403)

    def test_production_readiness(self):
        response = self.client.get("/v1/production/readiness")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("ready_for_production", body)
        self.assertIn("checks", body)

    def test_ui_served(self):
        response = self.client.get("/ui")
        self.assertEqual(response.status_code, 200)
        self.assertIn('dir="rtl"', response.text)

    def test_ui_asset_traversal_blocked(self):
        response = self.client.get("/ui/..%2Fapp%2Fconfig.py")
        self.assertIn(response.status_code, (404, 422))

    def test_openapi_lists_required_endpoints(self):
        spec = self.client.get("/openapi.json").json()
        paths = spec["paths"]
        for endpoint in (
            "/v1/assess", "/v1/assess/file", "/v1/assess/vision",
            "/v1/assistant/suggest", "/v1/rules", "/v1/health", "/v1/version",
            "/v1/design/suggest", "/v1/permit/readiness", "/v1/bim/review",
            "/v1/report/generate", "/v1/regulatory-resources",
            "/v1/regulatory-resources/summary", "/v1/rule-candidates/from-resources",
            "/v1/rule-candidates/review-package", "/v1/rule-candidates/review/validate",
            "/v1/rule-candidates/review/export-draft-rules", "/v1/production/readiness",
        ):
            self.assertIn(endpoint, paths, f"missing endpoint {endpoint}")


if __name__ == "__main__":
    unittest.main()
