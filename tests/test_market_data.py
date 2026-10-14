import io
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from urllib.error import HTTPError

import market_data


def request_scope(country="CHN", industry="manufacturing", start=2020, end=2025):
    return {
        "country_code": country,
        "industry_code": industry,
        "province_city": "上海",
        "occupation_code": "CN-ISCO-731",
        "seniority": "mid",
        "start_year": start,
        "end_year": end,
    }


def wb_payload(indicator, year=2025, value=None):
    if value is None:
        value = 24.2 if indicator.endswith(".ZS") else 3.2
    return [
        {"page": 1, "pages": 1, "per_page": 100, "total": 1},
        [{"date": str(year), "value": value}],
    ]


class FakeResponse:
    def __init__(self, payload):
        self.body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.body


class MarketDataTests(unittest.TestCase):
    def setUp(self):
        market_data.clear_public_cache()
        self.now = datetime(2026, 10, 14, 4, 0, tzinfo=timezone.utc)
        self.sleep = patch("market_data.time.sleep")
        self.sleep.start()
        self.addCleanup(self.sleep.stop)

    def enabled_scope(self, scope_a=None, scope_b=None, **extra):
        return {
            "enabled": True,
            "paths": {
                "A": scope_a or request_scope(),
                "B": scope_b or request_scope(),
            },
            **extra,
        }

    def mock_world_bank(self, year=2025):
        def open_url(request, timeout):
            self.assertEqual(timeout, market_data.REQUEST_TIMEOUT_SECONDS)
            indicator = request.full_url.split("/indicator/")[1].split("?")[0]
            return FakeResponse(wb_payload(indicator, year=year))

        return patch("market_data.urlopen", side_effect=open_url)

    def test_unselected_or_incomplete_scope_makes_no_external_request(self):
        with patch("market_data.urlopen") as open_url:
            disabled = market_data.fetch_comparison_evidence(None, now=self.now)
            incomplete = market_data.fetch_comparison_evidence(
                self.enabled_scope(scope_b={"country_code": "CHN"}), now=self.now
            )

        self.assertEqual(disabled["status"], "disabled")
        self.assertEqual(incomplete["status"], "incomplete_scope")
        self.assertIn("未发送外部请求", incomplete["message"])
        open_url.assert_not_called()

    def test_data_response_keeps_source_unit_scope_time_and_retrieval_metadata(self):
        with self.mock_world_bank():
            result = market_data.fetch_comparison_evidence(self.enabled_scope(), now=self.now)

        path = result["paths"][0]
        metric = path["metrics"][0]
        self.assertEqual(result["status"], "available")
        self.assertEqual(metric["source_name"], market_data.SOURCE_NAME)
        self.assertEqual(metric["unit"], "% of GDP")
        self.assertEqual(metric["country_code"], "CHN")
        self.assertEqual(metric["industry_code"], "manufacturing")
        self.assertEqual((metric["period_start"], metric["period_end"]), (2020, 2025))
        self.assertEqual(metric["observation_year"], 2025)
        self.assertIsNone(metric["published_at"])
        self.assertEqual(metric["freshness_status"], "current")
        self.assertEqual(metric["retrieved_at"], path["retrieved_at"])
        self.assertIn("未提供", metric["publication_note"])
        self.assertEqual(path["retrieved_at"], "2026-10-14T04:00:00Z")
        self.assertIn("data.worldbank.org/indicator/", metric["source_url"])
        self.assertIn("api.worldbank.org/v2", metric["api_url"])
        self.assertIn("CC BY 4.0", metric["license"])

    def test_upstream_urls_only_contain_allowlisted_country_indicator_and_years(self):
        scope = self.enabled_scope(
            **{
                "path_label_a": "PRIVATE-PATH-A",
                "background": "PRIVATE-BACKGROUND",
                "ratings": {"growth": 5, "stability": 1},
            }
        )
        scope["paths"]["A"]["private_note"] = "PRIVATE-NOTE"
        urls = []

        def open_url(request, timeout):
            urls.append(request.full_url)
            indicator = request.full_url.split("/indicator/")[1].split("?")[0]
            return FakeResponse(wb_payload(indicator))

        with patch("market_data.urlopen", side_effect=open_url):
            market_data.fetch_comparison_evidence(scope, now=self.now)

        self.assertEqual(len(urls), 2)
        for url in urls:
            self.assertIn("/country/CHN/indicator/", url)
            self.assertIn("date=2020:2025", url)
            self.assertNotIn("PRIVATE", url)
            self.assertNotIn("ratings", url)
            self.assertNotIn("Shanghai", url)

    def test_timeout_returns_unavailable_without_inventing_values(self):
        with patch("market_data.urlopen", side_effect=TimeoutError("timed out")):
            result = market_data.fetch_comparison_evidence(self.enabled_scope(), now=self.now)

        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["paths"][0]["status"], "unavailable")
        self.assertEqual(result["paths"][0]["metrics"], [])
        self.assertEqual(result["paths"][0]["failure_details"], ["network_error"])

    def test_http_429_is_reported_as_rate_limited_after_bounded_retry(self):
        def rate_limit(request, timeout):
            raise HTTPError(request.full_url, 429, "Too Many Requests", None, io.BytesIO())

        scope = self.enabled_scope(scope_b=request_scope(country="USA"))
        with patch("market_data.urlopen", side_effect=rate_limit) as open_url:
            result = market_data.fetch_comparison_evidence(scope, now=self.now)

        self.assertEqual(result["status"], "rate_limited")
        self.assertEqual(result["paths"][0]["status"], "rate_limited")
        self.assertEqual(open_url.call_count, 8)

    def test_no_data_response_stays_empty(self):
        with patch("market_data.urlopen", return_value=FakeResponse([{"page": 1, "total": 0}, None])):
            result = market_data.fetch_comparison_evidence(self.enabled_scope(), now=self.now)

        self.assertEqual(result["status"], "no_data")
        self.assertEqual(result["paths"][0]["metrics"], [])

    def test_old_observations_are_marked_stale_and_kept_as_observed(self):
        with self.mock_world_bank(year=2022):
            result = market_data.fetch_comparison_evidence(self.enabled_scope(), now=self.now)

        path = result["paths"][0]
        self.assertEqual(path["status"], "stale")
        self.assertEqual(result["status"], "stale")
        self.assertEqual(path["freshness_status"], "stale")
        self.assertEqual(path["metrics"][0]["value"], 24.2)
        self.assertEqual(path["metrics"][0]["observation_year"], 2022)
        self.assertEqual(path["metrics"][0]["freshness_status"], "stale")

    def test_malformed_response_does_not_create_default_metric_values(self):
        with patch("market_data.urlopen", return_value=FakeResponse({"unexpected": "shape"})):
            result = market_data.fetch_comparison_evidence(self.enabled_scope(), now=self.now)

        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["paths"][0]["metrics"], [])
        self.assertEqual(result["paths"][0]["failure_details"], ["invalid_response"])

    def test_different_indicators_units_or_periods_are_not_comparable(self):
        base = {
            "indicator_code": "NV.IND.MANF.ZS",
            "unit": "% of GDP",
            "period_start": 2020,
            "period_end": 2025,
            "observation_year": 2025,
        }
        other = dict(base, indicator_code="NV.SRV.TOTL.ZS")
        self.assertFalse(market_data.assess_metric_comparability(base, other)["comparable"])
        other = dict(base, unit="USD / year")
        self.assertIn("单位", market_data.assess_metric_comparability(base, other)["reason"])
        other = dict(base, period_end=2024)
        self.assertIn("时间范围", market_data.assess_metric_comparability(base, other)["reason"])
        other = dict(base, observation_year=2024)
        self.assertIn("观测年份", market_data.assess_metric_comparability(base, other)["reason"])

    def test_same_indicator_and_same_period_can_be_compared(self):
        a = {
            "indicator_code": "NV.IND.MANF.ZS",
            "unit": "% of GDP",
            "period_start": 2020,
            "period_end": 2025,
            "observation_year": 2025,
        }
        b = dict(a, country_code="USA")

        result = market_data.assess_metric_comparability(a, b)
        self.assertTrue(result["comparable"])
        self.assertTrue(result["geography_differs"])
        self.assertIn("跨国国家级宏观对照", result["reason"])
        self.assertIn("不能据此推断本地岗位", result["reason"])


if __name__ == "__main__":
    unittest.main()
