import unittest

from app.governance.catalog import list_resources, summary, validate_catalog
from app.governance.rule_candidates import (
    export_draft_rules, generate_candidates, review_package, validate_reviews,
)

VALID_REVIEW = {
    "candidate_id": "CAND-SBC-1001",
    "decision": "approve",
    "clause": "Section 4.2.1 (verified against official PDF)",
    "last_reviewed_date": "2026-07-20",
    "confidence_level": "high",
    "validated_by": "Eng. Test Reviewer, SCE License 12345",
    "category": "setbacks",
    "check": {"type": "min", "field": "setback_front_m", "value": 3.0},
}


class TestCatalog(unittest.TestCase):
    def test_catalog_is_well_formed(self):
        self.assertEqual(validate_catalog(), [])

    def test_draft_and_consultation_never_binding(self):
        for res in list_resources():
            if res["status"] in ("draft", "consultation"):
                self.assertFalse(res["binding"], res["id"])

    def test_every_resource_has_governance_fields(self):
        for res in list_resources():
            for field in ("source_reference", "last_reviewed_date", "confidence_level", "priority"):
                self.assertTrue(res.get(field), f"{res['id']} missing {field}")

    def test_priorities_are_valid(self):
        for res in list_resources():
            self.assertIn(res["priority"], ("P0", "P1", "P2"))

    def test_summary_counts(self):
        result = summary()
        self.assertEqual(result["total"], len(list_resources()))
        self.assertEqual(result["catalog_problems"], [])


class TestRuleCandidates(unittest.TestCase):
    def test_candidates_generated_for_all_resources(self):
        candidates = generate_candidates()
        self.assertEqual(len(candidates), len(list_resources()))

    def test_non_binding_sources_not_exportable(self):
        for cand in generate_candidates():
            if cand["source_status"] in ("draft", "consultation"):
                self.assertFalse(cand["exportable"], cand["candidate_id"])

    def test_no_candidate_is_auto_approved(self):
        for cand in generate_candidates():
            self.assertEqual(cand["review_status"], "pending_professional_review")

    def test_review_package_lists_required_fields(self):
        package = review_package()
        for field in ("clause", "last_reviewed_date", "confidence_level", "validated_by"):
            self.assertIn(field, package["required_fields"])


class TestReviewValidation(unittest.TestCase):
    def test_complete_review_validates(self):
        result = validate_reviews([VALID_REVIEW])
        self.assertEqual(result["results"][0]["outcome"], "validated_draft")

    def test_incomplete_review_rejected(self):
        incomplete = dict(VALID_REVIEW, clause="")
        result = validate_reviews([incomplete])
        self.assertEqual(result["results"][0]["outcome"], "incomplete")

    def test_non_binding_source_rejected_even_if_complete(self):
        draft_review = dict(VALID_REVIEW, candidate_id="CAND-SBC-DRAFT-UPDATE")
        result = validate_reviews([draft_review])
        self.assertEqual(result["results"][0]["outcome"], "rejected_non_binding_source")

    def test_bad_date_rejected(self):
        bad = dict(VALID_REVIEW, last_reviewed_date="20/07/2026")
        result = validate_reviews([bad])
        self.assertEqual(result["results"][0]["outcome"], "incomplete")

    def test_unknown_candidate(self):
        result = validate_reviews([dict(VALID_REVIEW, candidate_id="CAND-NOPE")])
        self.assertEqual(result["results"][0]["outcome"], "unknown_candidate")


class TestDraftExport(unittest.TestCase):
    def test_exported_rules_are_always_inactive_and_unofficial(self):
        result = export_draft_rules([VALID_REVIEW])
        self.assertEqual(result["exported_count"], 1)
        for rule in result["draft_rules"]:
            self.assertFalse(rule["is_active"])
            self.assertFalse(rule["is_official"])
            self.assertEqual(rule["status"], "validated_draft")
            for field in ("source_reference", "clause", "last_reviewed_date",
                          "confidence_level", "validated_by"):
                self.assertTrue(rule["governance"][field])

    def test_incomplete_reviews_are_skipped_not_exported(self):
        result = export_draft_rules([dict(VALID_REVIEW, validated_by="")])
        self.assertEqual(result["exported_count"], 0)
        self.assertEqual(len(result["skipped"]), 1)

    def test_rejected_reviews_not_exported(self):
        result = export_draft_rules([dict(VALID_REVIEW, decision="reject")])
        self.assertEqual(result["exported_count"], 0)


if __name__ == "__main__":
    unittest.main()
