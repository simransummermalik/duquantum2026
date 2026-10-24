import math
import unittest

from qpet.dynamiqs_adapter import CatParameters


class CatParameterTests(unittest.TestCase):
    def test_parameters_are_in_challenge_units(self):
        params = CatParameters()
        self.assertAlmostEqual(params.g2 / (2 * math.pi), 0.763)
        self.assertAlmostEqual(params.kappa_b / (2 * math.pi), 2.6)
        self.assertAlmostEqual(params.alpha**2, 4.41)

    def test_model_ratios_are_exposed_for_model_advice(self):
        ratios = CatParameters().ratios()
        self.assertAlmostEqual(ratios["g2_over_kappa_b"], 0.763 / 2.6, places=12)
        self.assertGreater(ratios["eps_d_over_kappa_b"], 1.0)


if __name__ == "__main__":
    unittest.main()
