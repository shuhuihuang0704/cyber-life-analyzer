import unittest
import re
from unittest.mock import patch

from app import app


class AnalyzeEndpointTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def test_homepage_uses_explicit_example_instead_of_prefilled_choices(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'id="load-example-button"', response.data)
        self.assertIn(b'placeholder="\xe4\xbe\x8b\xe5\xa6\x82', response.data)
        self.assertNotIn(b'value="\xe6\x8d\xa2\xe4\xb8\x80\xe4\xbb\xbd', response.data)
        self.assertNotIn(b"<canvas", response.data)

    def test_market_lookup_is_opt_in_and_country_industry_scopes_start_blank(self):
        response = self.client.get("/")
        markup = response.data.decode("utf-8")

        toggle = re.search(r'<input id="market-enabled"[^>]*>', markup)
        self.assertIsNotNone(toggle)
        self.assertNotIn("checked", toggle.group(0))
        for scope in ("a", "b"):
            self.assertRegex(
                markup,
                rf'<select name="market_{scope}_country">\s*<option value="">',
            )
            self.assertRegex(
                markup,
                rf'<select name="market_{scope}_industry">\s*<option value="">',
            )

    def test_empty_background_is_accepted(self):
        response = self.client.post(
            "/api/analyze",
            json={
                "option_a": "读研",
                "option_b": "先工作",
                "context": "",
                "risk_tolerance": 3,
                "resources": 3,
                "urgency": 3,
                "path_ratings": {
                    "A": {"growth": 4, "stability": 2, "cost": 4, "reversibility": 3},
                    "B": {"growth": 3, "stability": 4, "cost": 2, "reversibility": 4},
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["input"]["context"], "")
        self.assertIn("market_evidence", response.get_json())
        self.assertEqual(response.get_json()["market_evidence"]["status"], "disabled")

    def test_invalid_rating_returns_actionable_error(self):
        response = self.client.post(
            "/api/analyze",
            json={
                "option_a": "读研",
                "option_b": "先工作",
                "context": "",
                "risk_tolerance": 3,
                "resources": 3,
                "urgency": 3,
                "path_ratings": {
                    "A": {"growth": 4, "stability": 2, "cost": 8, "reversibility": 3},
                    "B": {"growth": 3, "stability": 4, "cost": 2, "reversibility": 4},
                },
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("成本负担", response.get_json()["error"])

    def test_no_market_scope_finishes_local_analysis_without_network_access(self):
        payload = {
            "option_a": "PRIVATE-PATH-A",
            "option_b": "PRIVATE-PATH-B",
            "context": "PRIVATE-BACKGROUND",
            "risk_tolerance": 3,
            "resources": 3,
            "urgency": 3,
            "path_ratings": {
                "A": {"growth": 4, "stability": 2, "cost": 4, "reversibility": 3},
                "B": {"growth": 3, "stability": 4, "cost": 2, "reversibility": 4},
            },
        }

        with patch("market_data.urlopen") as open_url:
            response = self.client.post("/api/analyze", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["market_evidence"]["status"], "disabled")
        self.assertEqual(len(response.get_json()["paths"]), 2)
        open_url.assert_not_called()

    def test_market_evidence_does_not_change_local_scores(self):
        payload = {
            "option_a": "PRIVATE-PATH-A",
            "option_b": "PRIVATE-PATH-B",
            "context": "PRIVATE-BACKGROUND",
            "risk_tolerance": 3,
            "resources": 3,
            "urgency": 3,
            "path_ratings": {
                "A": {"growth": 4, "stability": 2, "cost": 4, "reversibility": 3},
                "B": {"growth": 3, "stability": 4, "cost": 2, "reversibility": 4},
            },
        }
        local = self.client.post("/api/analyze", json=payload).get_json()
        market_scope = {
            "enabled": True,
            "paths": {
                "A": {
                    "country_code": "CHN",
                    "industry_code": "manufacturing",
                    "start_year": 2020,
                    "end_year": 2025,
                },
                "B": {
                    "country_code": "USA",
                    "industry_code": "services",
                    "start_year": 2020,
                    "end_year": 2025,
                },
            },
        }
        payload["market_scope"] = market_scope
        evidence = {"status": "available", "paths": [{"metrics": [{"value": 999}]}]}

        with patch("app.fetch_comparison_evidence", return_value=evidence) as fetch_evidence:
            combined = self.client.post("/api/analyze", json=payload).get_json()

        self.assertEqual(local["paths"], combined["paths"])
        self.assertEqual(local["comparison"], combined["comparison"])
        self.assertEqual(combined["market_evidence"], evidence)
        fetch_evidence.assert_called_once_with(market_scope)

    def test_provider_receives_only_the_structured_market_scope(self):
        scope = {
            "enabled": True,
            "paths": {
                "A": {
                    "country_code": "CHN",
                    "province_city": "上海",
                    "industry_code": "manufacturing",
                    "occupation_code": "ISCO-123",
                    "seniority": "mid",
                    "start_year": 2020,
                    "end_year": 2025,
                },
                "B": {
                    "country_code": "USA",
                    "province_city": "Seattle",
                    "industry_code": "services",
                    "occupation_code": "ISCO-456",
                    "seniority": "senior",
                    "start_year": 2020,
                    "end_year": 2025,
                },
            },
        }
        payload = {
            "option_a": "PRIVATE-PATH-A",
            "option_b": "PRIVATE-PATH-B",
            "context": "PRIVATE-BACKGROUND",
            "risk_tolerance": 4,
            "resources": 2,
            "urgency": 5,
            "path_ratings": {
                "A": {"growth": 5, "stability": 1, "cost": 3, "reversibility": 2},
                "B": {"growth": 1, "stability": 5, "cost": 2, "reversibility": 4},
            },
            "market_scope": scope,
        }

        with patch("app.fetch_comparison_evidence", return_value={"status": "available"}) as fetch_evidence:
            response = self.client.post("/api/analyze", json=payload)

        self.assertEqual(response.status_code, 200)
        fetch_evidence.assert_called_once_with(scope)
        self.assertNotIn("PRIVATE-PATH-A", repr(fetch_evidence.call_args))
        self.assertNotIn("PRIVATE-BACKGROUND", repr(fetch_evidence.call_args))
        self.assertNotIn("'growth': 5", repr(fetch_evidence.call_args))


if __name__ == "__main__":
    unittest.main()
