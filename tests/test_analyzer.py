import unittest
from itertools import product

from analyzer import AnalysisInputError, analyze_paths


def payload():
    return {
        "option_a": "转向新的岗位",
        "option_b": "留在当前岗位",
        "context": "",
        "risk_tolerance": 3,
        "resources": 3,
        "urgency": 3,
        "path_ratings": {
            "A": {"growth": 5, "stability": 2, "cost": 3, "reversibility": 4},
            "B": {"growth": 2, "stability": 5, "cost": 2, "reversibility": 3},
        },
    }


class AnalyzePathsTests(unittest.TestCase):
    def test_same_structured_input_is_deterministic(self):
        first = analyze_paths(payload())
        second = analyze_paths(payload())

        self.assertEqual(first["paths"], second["paths"])
        self.assertEqual(first["recommendation"], second["recommendation"])

    def test_background_note_does_not_change_scores(self):
        first = payload()
        second = payload()
        first["context"] = "context-9"
        second["context"] = "context-10"

        self.assertEqual(
            [path["fit_score"] for path in analyze_paths(first)["paths"]],
            [path["fit_score"] for path in analyze_paths(second)["paths"]],
        )

    def test_empty_background_is_allowed(self):
        result = analyze_paths(payload())

        self.assertEqual(result["input"]["context"], "")

    def test_equal_ratings_do_not_force_a_winner(self):
        data = payload()
        data["path_ratings"]["A"] = {key: 3 for key in ("growth", "stability", "cost", "reversibility")}
        data["path_ratings"]["B"] = {key: 3 for key in ("growth", "stability", "cost", "reversibility")}

        result = analyze_paths(data)

        self.assertEqual(result["comparison"]["status"], "balanced")
        self.assertIsNone(result["recommendation"]["preferred_path"])

    def test_small_score_gap_does_not_force_a_winner(self):
        data = payload()
        data["path_ratings"]["A"] = {"growth": 3, "stability": 3, "cost": 3, "reversibility": 4}
        data["path_ratings"]["B"] = {"growth": 3, "stability": 3, "cost": 3, "reversibility": 3}

        result = analyze_paths(data)

        self.assertLess(result["comparison"]["score_gap"], 6)
        self.assertEqual(result["comparison"]["status"], "balanced")
        self.assertIsNone(result["recommendation"]["preferred_path"])

    def test_weights_are_explainable_and_sum_to_one_hundred(self):
        result = analyze_paths(payload())

        self.assertEqual(sum(result["scoring"]["weights"].values()), 100)
        self.assertEqual(
            {item["key"] for item in result["paths"][0]["breakdown"]},
            {"growth", "stability", "cost", "reversibility"},
        )

    def test_preferences_adjust_the_documented_weights(self):
        neutral = analyze_paths(payload())["scoring"]["weights"]
        data = payload()
        data.update(risk_tolerance=5, resources=1, urgency=5)
        adjusted = analyze_paths(data)["scoring"]["weights"]

        self.assertEqual(neutral, {"growth": 30, "stability": 25, "cost": 25, "reversibility": 20})
        self.assertEqual(adjusted, {"growth": 34, "stability": 17, "cost": 33, "reversibility": 16})
        self.assertEqual(sum(adjusted.values()), 100)

    def test_sensitivity_marks_a_leader_flip_under_nearby_risk_preferences(self):
        data = payload()
        data["path_ratings"]["A"] = {
            "growth": 5,
            "stability": 1,
            "cost": 3,
            "reversibility": 3,
        }
        data["path_ratings"]["B"] = {
            "growth": 1,
            "stability": 5,
            "cost": 3,
            "reversibility": 4,
        }

        result = analyze_paths(data)

        self.assertIn("sensitivity", result)
        self.assertEqual(result["sensitivity"]["status"], "sensitive")
        self.assertIn("risk_tolerance", result["sensitivity"]["changed_preferences"])
        self.assertIn("改变", result["sensitivity"]["summary"])

    def test_sensitivity_does_not_flag_stable_preferences(self):
        data = payload()
        data["path_ratings"]["A"] = {key: 5 for key in ("growth", "stability", "cost", "reversibility")}
        data["path_ratings"]["B"] = {key: 1 for key in ("growth", "stability", "cost", "reversibility")}

        result = analyze_paths(data)

        self.assertIn("sensitivity", result)
        self.assertEqual(result["sensitivity"]["status"], "stable")
        self.assertEqual(result["sensitivity"]["changed_preferences"], [])

    def test_all_preference_combinations_keep_positive_weights(self):
        for risk, resources, urgency in product(range(1, 6), repeat=3):
            data = payload()
            data.update(risk_tolerance=risk, resources=resources, urgency=urgency)

            weights = analyze_paths(data)["scoring"]["weights"]

            self.assertTrue(all(weight > 0 for weight in weights.values()))
            self.assertEqual(sum(weights.values()), 100)

    def test_recommendation_contains_all_90_day_decision_parts(self):
        recommendation = analyze_paths(payload())["recommendation"]

        for key in ("experiment", "metric", "continue_if", "pause_if"):
            self.assertTrue(recommendation[key])

    def test_invalid_path_rating_is_rejected(self):
        data = payload()
        data["path_ratings"]["A"]["cost"] = 6

        with self.assertRaisesRegex(AnalysisInputError, "成本负担"):
            analyze_paths(data)

    def test_whitespace_only_path_name_is_rejected(self):
        data = payload()
        data["option_a"] = " \t "

        with self.assertRaisesRegex(AnalysisInputError, "路径 A 不能为空"):
            analyze_paths(data)

    def test_path_name_limit_counts_raw_browser_characters_before_trimming(self):
        data = payload()
        data["option_a"] = f" {'a' * 79} "

        with self.assertRaisesRegex(AnalysisInputError, "80 个字符以内"):
            analyze_paths(data)

    def test_text_limits_match_browser_utf16_length(self):
        data = payload()
        data["option_a"] = "😀" * 41

        with self.assertRaisesRegex(AnalysisInputError, "80 个字符以内"):
            analyze_paths(data)

        data = payload()
        data["context"] = "😀" * 151

        with self.assertRaisesRegex(AnalysisInputError, "300 个字符以内"):
            analyze_paths(data)


if __name__ == "__main__":
    unittest.main()
