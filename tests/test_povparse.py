import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools", "render"))
import povparse


class TestPovParse(unittest.TestCase):
    def test_box(self):
        s = povparse.parse("box { <0,1,2>, <3,4,5> }")
        self.assertEqual(len(s), 1)
        self.assertEqual(s[0]["type"], "box")
        self.assertEqual(s[0]["lo"], (0.0, 1.0, 2.0))
        self.assertEqual(s[0]["hi"], (3.0, 4.0, 5.0))

    def test_cylinder_and_cone(self):
        s = povparse.parse("cylinder { <0,0,0>, <0,2,0>, 0.5 } "
                           "cone { <0,0,0>, 1.0 <0,3,0>, 0.25 }")
        self.assertEqual([x["type"] for x in s], ["cylinder", "cone"])
        self.assertAlmostEqual(s[0]["r"], 0.5)
        self.assertAlmostEqual(s[1]["ra"], 1.0)
        self.assertAlmostEqual(s[1]["rb"], 0.25)

    def test_sphere_with_scale_and_translate(self):
        s = povparse.parse("sphere { <0,0,0>, 0.4 scale <1,0.5,1> translate <2,3,4> }")[0]
        self.assertEqual(s["scale"], [(1.0, 0.5, 1.0)])
        self.assertEqual(s["translate"], [(2.0, 3.0, 4.0)])

    def test_superellipsoid(self):
        s = povparse.parse("superellipsoid { <0.25,0.25> scale <1,2,3> translate <0,1,0> }")[0]
        self.assertEqual(s["type"], "superellipsoid")
        self.assertEqual(s["e"], (0.25, 0.25))

    def test_csg_nesting(self):
        s = povparse.parse("difference { box { <0,0,0>, <1,1,1> } "
                           "sphere { <0,0,0>, 0.3 translate <1,1,1> } }")[0]
        self.assertEqual(s["type"], "difference")
        self.assertEqual([k["type"] for k in s["children"]], ["box", "sphere"])

    def test_unsupported_primitive_raises(self):
        # a new library primitive must fail loudly, not vanish from the scene
        with self.assertRaises(povparse.ParseError):
            povparse.parse("torus { 1.0, 0.2 }")

    def test_every_library_family_round_trips(self):
        """Whatever the component library emits, the parser must accept."""
        import library as LIB
        calls = [
            LIB.sofa(0, 0, 2.4, 0.9), LIB.armchair(0, 0, 0.9, 0.9),
            LIB.majlis_bench(0, 0, 3.0, 0.8), LIB.dining_table(0, 0, 1.6, 0.9),
            LIB.dining_chair(0, 0, 0.45, 0.45), LIB.coffee_table(0, 0, 1.1, 0.6),
            LIB.wardrobe(0, 0, 2.0, 0.6), LIB.bedside(0, 0, 0.45, 0.45),
            LIB.tv_unit(0, 0, 1.8, 0.45), LIB.console(0, 0, 1.4, 0.4),
            LIB.desk(0, 0, 1.2, 0.6), LIB.bed(0, 0, 1.8, 2.0),
            LIB.base_units(0, 0, 3.0, 0.6), LIB.wall_units(0, 0, 3.0, 0.35),
            LIB.sink(1, 1), LIB.hob(2, 1), LIB.fridge(0, 0, 0.7, 0.7),
            LIB.wc_pan(0, 0, 0.4, 0.6), LIB.basin(0, 0, 0.6, 0.45),
            LIB.shower(0, 0, 0.9, 0.9), LIB.rug(0, 0, 2.0, 1.4),
            LIB.pendant(1, 1, 3.0), LIB.curtain(0, 0, 1.6, 0.1, 2.4),
            LIB.artwork(0, 0, 0.9, 0.05), LIB.cushions(0, 0, 2.4, 0.9, "n"),
            LIB.throw(0, 0, 2.4, 0.9, "n"), LIB.book_stack(0, 0, 0.4),
            LIB.bowl(0, 0, 0.4), LIB.tray(0, 0, 0.4), LIB.vase(0, 0, 0.75),
            LIB.floor_lamp(0, 0), LIB.potted_plant(0, 0),
            LIB.table_lamp(0, 0, 0.5), LIB.bed_throw(0, 0, 1.8, 2.0, "n"),
            LIB.splashback(0, 0, 3.0, 0.1),
        ]
        for pieces in calls:
            for geo, _tex in pieces:
                if geo:
                    self.assertTrue(povparse.parse(geo), geo[:60])


if __name__ == "__main__":
    unittest.main()
