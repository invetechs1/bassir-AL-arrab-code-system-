"""Tests for the seven senior discipline agents and their coordinator."""

import unittest

from app.agents import AGENTS, list_agents, run_design
from app.agents.base import build_brief
from app.agents.orchestrator import AGENT_INDEX, coordinate

VILLA = {
    "project_name": "Test villa", "city": "الرياض", "building_type": "villa",
    "land_use": "residential", "plot_w": 20, "plot_d": 25,
    "sb_f": 3, "sb_s": 2, "sb_r": 2.5, "floors": 2, "floor_h": 3.2,
    "units": 1, "parking": 2,
}

TOWER = {
    "project_name": "Test block", "city": "جدة", "building_type": "apartment",
    "land_use": "residential", "plot_w": 30, "plot_d": 40,
    "sb_f": 4, "sb_s": 3, "sb_r": 3, "floors": 6, "floor_h": 3.4,
    "units": 24, "parking": 10,
}

EXPECTED_IDS = [
    "architecture", "structural", "mechanical",
    "electrical", "interior", "quantity", "regulation",
]


class TestRoster(unittest.TestCase):
    def test_seven_agents(self):
        self.assertEqual(len(AGENTS), 7)
        self.assertEqual([a.agent_id for a in AGENTS], EXPECTED_IDS)

    def test_every_agent_is_senior_and_named_in_both_languages(self):
        for agent in AGENTS:
            self.assertTrue(agent.name_ar.strip(), agent.agent_id)
            self.assertTrue(agent.name_en.strip(), agent.agent_id)
            self.assertIn("Senior", agent.name_en, agent.agent_id)

    def test_roster_endpoint_payload(self):
        roster = list_agents()
        self.assertEqual(roster["count"], 7)
        self.assertFalse(roster["official_basis"])
        self.assertIn("disclaimer", roster)

    def test_dependencies_only_reference_earlier_agents(self):
        seen = set()
        for agent in AGENTS:
            for dep in agent.depends_on:
                self.assertIn(dep, AGENT_INDEX, f"{agent.agent_id} depends on unknown {dep}")
                self.assertIn(dep, seen, f"{agent.agent_id} depends on {dep}, which runs later")
            seen.add(agent.agent_id)


class TestBrief(unittest.TestCase):
    def test_geometry_matches_setback_subtraction(self):
        brief = build_brief(VILLA)
        self.assertAlmostEqual(brief["plot_area"], 500.0)
        self.assertAlmostEqual(brief["build_w"], 20 - 2 * 2)
        self.assertAlmostEqual(brief["build_d"], 25 - 3 - 2.5)
        self.assertAlmostEqual(brief["gfa"], brief["footprint"] * 2)

    def test_degenerate_input_is_clamped_not_crashed(self):
        brief = build_brief({"plot_w": 0, "plot_d": -5, "floors": 0, "units": 0})
        self.assertGreater(brief["plot_w"], 0)
        self.assertGreater(brief["plot_d"], 0)
        self.assertGreaterEqual(brief["floors"], 1)
        self.assertGreaterEqual(brief["units"], 1)

    def test_junk_values_fall_back_to_defaults(self):
        brief = build_brief({"plot_w": "abc", "floors": None, "floor_h": float("nan")})
        self.assertGreater(brief["plot_w"], 0)
        self.assertGreaterEqual(brief["floor_h"], 2.4)

    def test_empty_params_do_not_crash(self):
        self.assertGreater(build_brief({})["gfa"], 0)
        self.assertGreater(build_brief(None)["gfa"], 0)


class TestDesignPackage(unittest.TestCase):
    def setUp(self):
        self.package = run_design(VILLA)

    def test_all_seven_agents_report(self):
        self.assertEqual([a["agent_id"] for a in self.package["agents"]], EXPECTED_IDS)

    def test_every_agent_package_is_complete(self):
        for agent in self.package["agents"]:
            for field in ("name_ar", "name_en", "summary_ar", "summary_en", "metrics"):
                self.assertTrue(agent.get(field), f"{agent['agent_id']} missing {field}")
            self.assertTrue(agent["metrics"], agent["agent_id"])
            for m in agent["metrics"]:
                self.assertTrue(m["key_ar"] and m["key_en"], agent["agent_id"])
                self.assertTrue(m["basis"], f"{agent['agent_id']} metric without a basis")

    def test_deterministic(self):
        self.assertEqual(run_design(VILLA), run_design(VILLA))

    def test_headline_is_populated(self):
        head = self.package["headline"]
        self.assertGreater(head["gfa_m2"], 0)
        self.assertGreater(head["cost_high_sar"], head["cost_low_sar"])
        self.assertGreater(head["months"], 0)

    def test_runs_for_every_building_type(self):
        for btype in ("villa", "apartment", "commercial", "mixed", "industrial"):
            params = dict(VILLA, building_type=btype)
            package = run_design(params)
            self.assertEqual(len(package["agents"]), 7, btype)
            self.assertGreater(package["headline"]["cost_low_sar"], 0, btype)


class TestGovernanceInvariants(unittest.TestCase):
    """The agents must never present their output as official."""

    def setUp(self):
        self.package = run_design(TOWER)

    def test_package_is_advisory_and_unofficial(self):
        self.assertTrue(self.package["advisory_only"])
        self.assertFalse(self.package["official_basis"])
        self.assertIn("disclaimer", self.package)
        self.assertIn("ar", self.package["disclaimer"])
        self.assertIn("en", self.package["disclaimer"])

    def test_each_agent_is_advisory_and_unofficial(self):
        for agent in self.package["agents"]:
            self.assertTrue(agent["advisory_only"], agent["agent_id"])
            self.assertFalse(agent["official_basis"], agent["agent_id"])

    def test_every_agent_declares_assumptions_and_verification(self):
        for agent in self.package["agents"]:
            if agent["agent_id"] == "regulation":
                continue
            self.assertTrue(agent["assumptions"], agent["agent_id"])
            self.assertTrue(agent["verify"], agent["agent_id"])

    def test_regulation_applies_no_official_rules(self):
        reg = AGENT_INDEX["regulation"]
        package = next(a for a in self.package["agents"] if a["agent_id"] == reg.agent_id)
        self.assertEqual(package["outputs"]["official_rules_applied"], 0)
        for finding in package["assessment"]["findings"]:
            self.assertFalse(finding["is_official"], finding["rule_code"])

    def test_verification_register_collects_every_discipline(self):
        package = next(a for a in self.package["agents"] if a["agent_id"] == "regulation")
        raised_by = {item["agent_id"] for item in package["register"]}
        for agent_id in ("architecture", "structural", "electrical", "mechanical", "interior", "quantity"):
            self.assertIn(agent_id, raised_by)


class TestQuantitySurveyor(unittest.TestCase):
    def setUp(self):
        self.package = next(a for a in run_design(VILLA)["agents"] if a["agent_id"] == "quantity")

    def test_rates_are_ranges_never_a_single_price(self):
        for element in self.package["schedule"]:
            self.assertLess(element["rate_low"], element["rate_high"], element["key"])
            self.assertLess(element["cost_low"], element["cost_high"], element["key"])

    def test_cost_builds_up_through_vat(self):
        out = self.package["outputs"]
        self.assertLess(out["works_low"], out["net_low"])
        self.assertLess(out["net_low"], out["total_low"])
        self.assertLess(out["net_high"], out["total_high"])

    def test_cashflow_shares_sum_to_one(self):
        self.assertAlmostEqual(sum(p["share"] for p in self.package["cashflow"]), 1.0, places=6)

    def test_states_that_rates_are_not_quotations(self):
        blob = " ".join(r["en"].lower() for r in self.package["recommendations"])
        self.assertIn("not quotations", blob)


class TestCoordination(unittest.TestCase):
    def test_large_electrical_load_flags_a_missing_substation_room(self):
        package = run_design(TOWER)
        ids = {i["id"] for i in package["coordination"]["issues"]}
        self.assertIn("substation-room", ids)

    def test_shallow_floor_height_flags_a_clear_height_clash(self):
        package = run_design(dict(VILLA, floor_h=2.8))
        issue = next(i for i in package["coordination"]["issues"] if i["id"] == "clear-height")
        self.assertEqual(issue["severity"], "high")
        self.assertIn("interior", issue["disciplines"])

    def test_generous_floor_height_clears_the_clash(self):
        package = run_design(dict(VILLA, floor_h=4.2))
        ids = {i["id"] for i in package["coordination"]["issues"]}
        self.assertNotIn("clear-height", ids)

    def test_parking_beyond_the_open_site_is_flagged(self):
        package = run_design(dict(VILLA, sb_f=0.5, sb_s=0.5, sb_r=0.5, units=20, parking=20))
        ids = {i["id"] for i in package["coordination"]["issues"]}
        self.assertIn("parking-area", ids)

    def test_coastal_exposure_reaches_the_cost_plan(self):
        package = run_design(dict(VILLA, city="الدمام"))
        ids = {i["id"] for i in package["coordination"]["issues"]}
        self.assertIn("coastal-cost", ids)

    def test_every_issue_is_bilingual_and_actionable(self):
        for params in (VILLA, TOWER):
            for issue in run_design(params)["coordination"]["issues"]:
                self.assertTrue(issue["ar"] and issue["en"], issue["id"])
                self.assertTrue(issue["action_ar"] and issue["action_en"], issue["id"])
                self.assertIn(issue["severity"], ("high", "medium", "low"))
                self.assertGreaterEqual(len(issue["disciplines"]), 2, issue["id"])

    def test_counts_match_the_issue_list(self):
        package = run_design(TOWER)
        co = package["coordination"]
        self.assertEqual(co["total"], len(co["issues"]))
        self.assertEqual(sum(co["counts"].values()), co["total"])

    def test_coordination_tolerates_empty_packages(self):
        self.assertEqual(coordinate(build_brief(VILLA), {}), [])


class TestDisciplineOutputsFeedForward(unittest.TestCase):
    """Later agents must actually consume what earlier ones produced."""

    def setUp(self):
        self.agents = {a["agent_id"]: a for a in run_design(TOWER)["agents"]}

    def test_electrical_hvac_load_tracks_the_mechanical_tonnage(self):
        tons = self.agents["mechanical"]["outputs"]["tons"]
        hvac_kw = self.agents["electrical"]["outputs"]["hvac_kw"]
        self.assertAlmostEqual(hvac_kw, tons * 1.1, places=1)

    def test_interior_clear_height_uses_the_structural_slab(self):
        slab_mm = self.agents["structural"]["outputs"]["slab_mm"]
        interior = self.agents["interior"]["outputs"]
        expected = TOWER["floor_h"] - slab_mm / 1000.0 - interior["service_void_m"]
        self.assertAlmostEqual(interior["clear_height_m"], round(expected, 2), places=2)

    def test_interior_finishes_cover_the_architectural_program(self):
        self.assertEqual(
            len(self.agents["interior"]["schedule"]),
            len(self.agents["architecture"]["schedule"]),
        )

    def test_coastal_city_raises_the_concrete_grade(self):
        inland = run_design(dict(VILLA, city="الرياض"))
        coastal = run_design(dict(VILLA, city="جدة"))
        grade_of = lambda p: next(a for a in p["agents"] if a["agent_id"] == "structural")["outputs"]["grade"]
        self.assertNotEqual(grade_of(inland), grade_of(coastal))


if __name__ == "__main__":
    unittest.main()
