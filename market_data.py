"""Optional, public World Bank industry indicators kept separate from scoring."""

from __future__ import annotations

import json
import math
import threading
import time
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


SOURCE_NAME = "World Bank World Development Indicators (WDI)"
API_BASE = "https://api.worldbank.org/v2"
API_DOCUMENTATION = "https://datahelpdesk.worldbank.org/knowledgebase/articles/889392-about-the-indicators-api-documentation"
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
CACHE_TTL_SECONDS = 6 * 60 * 60
REQUEST_TIMEOUT_SECONDS = 5
MAX_RETRIES = 1
_cache: dict[tuple[str, str, int, int], tuple[float, dict[str, Any], str]] = {}
_cache_lock = threading.Lock()

COUNTRIES = {
    "CHN": "中国",
    "USA": "美国",
    "DEU": "德国",
    "GBR": "英国",
    "FRA": "法国",
    "JPN": "日本",
    "IND": "印度",
    "CAN": "加拿大",
    "AUS": "澳大利亚",
    "KOR": "韩国",
    "SGP": "新加坡",
    "BRA": "巴西",
}

# World Bank WDI sector aggregates, not detailed occupation or vacancy classifications.
INDUSTRIES = {
    "agriculture": {
        "label": "农业、林业和渔业",
        "share": ("NV.AGR.TOTL.ZS", "增加值占 GDP", "% of GDP"),
        "growth": ("NV.AGR.TOTL.KD.ZG", "增加值年度增速", "annual % growth"),
    },
    "industry": {
        "label": "工业（含建筑业）",
        "share": ("NV.IND.TOTL.ZS", "增加值占 GDP", "% of GDP"),
        "growth": ("NV.IND.TOTL.KD.ZG", "增加值年度增速", "annual % growth"),
    },
    "manufacturing": {
        "label": "制造业",
        "share": ("NV.IND.MANF.ZS", "增加值占 GDP", "% of GDP"),
        "growth": ("NV.IND.MANF.KD.ZG", "增加值年度增速", "annual % growth"),
    },
    "services": {
        "label": "服务业",
        "share": ("NV.SRV.TOTL.ZS", "增加值占 GDP", "% of GDP"),
        "growth": ("NV.SRV.TOTL.KD.ZG", "增加值年度增速", "annual % growth"),
    },
}

LIMITATION = (
    "这是国家级年度国民经济行业统计，不是岗位数量、招聘需求或职业薪资；"
    "不能代表城市或个人机会，也不构成未来预测。"
)


def clear_public_cache() -> None:
    """Clear the in-memory cache; useful for deterministic tests."""
    with _cache_lock:
        _cache.clear()


def _now_iso(now: datetime | None = None) -> str:
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _year(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if str(value).strip() != str(number) or not 1960 <= number <= datetime.now().year:
        return None
    return number


def _validated_query_scope(scope: Any) -> dict[str, Any] | None:
    if not isinstance(scope, dict):
        return None
    country_code = scope.get("country_code")
    industry_code = scope.get("industry_code")
    start_year = _year(scope.get("start_year"))
    end_year = _year(scope.get("end_year"))
    if (
        not isinstance(country_code, str)
        or country_code not in COUNTRIES
        or not isinstance(industry_code, str)
        or industry_code not in INDUSTRIES
        or start_year is None
        or end_year is None
        or start_year > end_year
        or end_year - start_year > 20
    ):
        return None
    # Return only explicit, allowlisted query parameters. Free text and ratings never enter this object.
    return {
        "country_code": country_code,
        "industry_code": industry_code,
        "start_year": start_year,
        "end_year": end_year,
    }


def _local_text(value: Any) -> str:
    """Keep optional display-only scope notes bounded and out of upstream URLs."""
    if not isinstance(value, str):
        return ""
    return value.strip()[:80]


def _request_json(url: str) -> tuple[dict[str, Any] | list[Any] | None, str | None]:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "CyberLifeAnalyzer/2.1"})
    for attempt in range(MAX_RETRIES + 1):
        try:
            with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                return json.loads(response.read().decode("utf-8")), None
        except HTTPError as exc:
            if attempt < MAX_RETRIES and (exc.code == 429 or 500 <= exc.code <= 599):
                time.sleep(0.1)
                continue
            if exc.code == 429:
                return None, "rate_limited"
            return None, "source_error"
        except (TimeoutError, URLError, OSError):
            if attempt < MAX_RETRIES:
                time.sleep(0.1)
                continue
            return None, "network_error"
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            return None, "invalid_response"
    return None, "network_error"


def _public_series(
    country_code: str,
    indicator_code: str,
    start_year: int,
    end_year: int,
    *,
    now: datetime | None = None,
) -> tuple[list[dict[str, Any]] | None, str | None, str, str, bool]:
    cache_key = (country_code, indicator_code, start_year, end_year)
    cache_now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached and cache_now - cached[0] <= CACHE_TTL_SECONDS:
            return cached[1].get("rows"), None, cached[2], cached[1]["url"], True

    date_range = f"{start_year}:{end_year}"
    url = (
        f"{API_BASE}/country/{country_code}/indicator/{quote(indicator_code, safe='.')}"
        f"?format=json&date={date_range}&per_page=100"
    )
    payload, error = _request_json(url)
    retrieved_at = _now_iso(now)
    if error:
        return None, error, retrieved_at, url, False
    if not isinstance(payload, list) or len(payload) < 2 or not isinstance(payload[0], dict):
        return None, "invalid_response", retrieved_at, url, False
    if payload[1] is None or payload[1] == []:
        rows: list[dict[str, Any]] = []
    elif isinstance(payload[1], list):
        rows = payload[1]
    else:
        return None, "invalid_response", retrieved_at, url, False
    with _cache_lock:
        _cache[cache_key] = (cache_now, {"rows": rows, "url": url}, retrieved_at)
    return rows, None, retrieved_at, url, False


def _normalize_series(
    rows: list[dict[str, Any]],
    *,
    metric_key: str,
    indicator_code: str,
    indicator_label: str,
    unit: str,
    country_code: str,
    industry_code: str,
    start_year: int,
    end_year: int,
) -> tuple[dict[str, Any] | None, str | None]:
    points = []
    for row in rows:
        if not isinstance(row, dict):
            return None, "invalid_response"
        year = row.get("date")
        value = row.get("value")
        if not isinstance(year, str) or not year.isdigit() or len(year) != 4:
            return None, "invalid_response"
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            return None, "invalid_response"
        point_year = int(year)
        if start_year <= point_year <= end_year:
            points.append({"year": point_year, "value": round(float(value), 4)})
    points.sort(key=lambda point: point["year"])
    if not points:
        return None, "no_data"
    latest = points[-1]
    indicator_url = f"https://data.worldbank.org/indicator/{indicator_code}"
    return (
        {
            "key": metric_key,
            "name": indicator_label,
            "indicator_code": indicator_code,
            "value": latest["value"],
            "unit": unit,
            "change_basis": "年度观测值；年度增速为相对上年的实际增加值变化率。" if metric_key == "annual_growth" else "该行业增加值占当年 GDP 的比例。",
            "observation_year": latest["year"],
            "period_start": start_year,
            "period_end": end_year,
            "series": points,
            "country_code": country_code,
            "industry_code": industry_code,
            "source_name": SOURCE_NAME,
            "source_url": indicator_url,
            "api_url": (
                f"{API_BASE}/country/{country_code}/indicator/{indicator_code}"
                f"?format=json&date={start_year}:{end_year}&per_page=100"
            ),
            "api_description": "World Bank Indicators API v2 · World Development Indicators",
            "license": "CC BY 4.0",
            "license_url": LICENSE_URL,
            "published_at": None,
            "publication_note": "API 未提供该观测值的单项发布日期。",
            "update_frequency": "年度国民账户统计；各国发布时间不同，源站修订可能回溯影响历史年份。",
            "limitation": LIMITATION,
        },
        None,
    )


def _path_evidence(
    path_id: str,
    submitted_scope: dict[str, Any],
    query_scope: dict[str, Any],
    *,
    now: datetime | None,
) -> dict[str, Any]:
    industry = INDUSTRIES[query_scope["industry_code"]]
    metrics = []
    failure_statuses = []
    cache_states = []
    retrieved_at = None
    for metric_key, spec in (
        ("value_added_share", industry["share"]),
        ("annual_growth", industry["growth"]),
    ):
        indicator_code, indicator_label, unit = spec
        rows, error, fetched_at, api_url, from_cache = _public_series(
            query_scope["country_code"],
            indicator_code,
            query_scope["start_year"],
            query_scope["end_year"],
            now=now,
        )
        retrieved_at = retrieved_at or fetched_at
        cache_states.append(from_cache)
        if error:
            failure_statuses.append(error)
            continue
        if not isinstance(rows, list):
            failure_statuses.append("invalid_response")
            continue
        metric, normalize_error = _normalize_series(
            rows,
            metric_key=metric_key,
            indicator_code=indicator_code,
            indicator_label=indicator_label,
            unit=unit,
            country_code=query_scope["country_code"],
            industry_code=query_scope["industry_code"],
            start_year=query_scope["start_year"],
            end_year=query_scope["end_year"],
        )
        if normalize_error:
            failure_statuses.append(normalize_error)
        elif metric:
            metric["api_url"] = api_url
            metric["retrieved_at"] = fetched_at
            metric["release_date"] = None
            metric["freshness_status"] = (
                "stale"
                if metric["observation_year"] < (now or datetime.now(timezone.utc)).year - 2
                else "current"
            )
            metrics.append(metric)

    country_code = query_scope["country_code"]
    latest_year = max((metric["observation_year"] for metric in metrics), default=None)
    current_year = (now or datetime.now(timezone.utc)).year
    if metrics and latest_year is not None:
        stale_count = sum(metric["freshness_status"] == "stale" for metric in metrics)
        freshness_status = (
            "stale" if stale_count == len(metrics)
            else "partial" if stale_count
            else "current"
        )
        status = (
            "stale" if freshness_status == "stale"
            else "partial" if failure_statuses or freshness_status == "partial"
            else "available"
        )
    elif failure_statuses and all(item == "no_data" for item in failure_statuses):
        freshness_status = "unknown"
        status = "no_data"
    elif failure_statuses:
        freshness_status = "unknown"
        status = "rate_limited" if "rate_limited" in failure_statuses else "unavailable"
    else:
        freshness_status = "unknown"
        status = "no_data"

    return {
        "id": path_id,
        "status": status,
        "country_code": country_code,
        "country": COUNTRIES[country_code],
        "province_city": _local_text(submitted_scope.get("province_city")),
        "industry_code": query_scope["industry_code"],
        "industry": industry["label"],
        "occupation_code": _local_text(submitted_scope.get("occupation_code")),
        "seniority": submitted_scope.get("seniority")
        if isinstance(submitted_scope.get("seniority"), str)
        and submitted_scope.get("seniority") in {"", "entry", "mid", "senior"}
        else "",
        "period_start": query_scope["start_year"],
        "period_end": query_scope["end_year"],
        "retrieved_at": retrieved_at,
        "update_frequency": "年度；各国国民账户数据发布时间不同，通常会滞后于当前年份。",
        "freshness_status": freshness_status,
        "freshness_label": {
            "current": "数据年份较新",
            "stale": "数据年份较旧",
            "partial": "部分指标年份较旧",
            "unknown": "无法判断新鲜度",
        }[freshness_status],
        "latest_observation_year": latest_year,
        "release_date": None,
        "publication_note": "源接口未提供单项发布日期；页面会显示观测年份与本次抓取时间。",
        "metrics": metrics,
        "source_name": SOURCE_NAME,
        "source_documentation": API_DOCUMENTATION,
        "license": "CC BY 4.0",
        "license_url": LICENSE_URL,
        "api_description": "World Bank Indicators API v2 · World Development Indicators",
        "limitation": LIMITATION,
        "failure_details": sorted(set(failure_statuses)),
        "from_cache": bool(cache_states) and all(cache_states),
    }


def assess_metric_comparability(metric_a: dict[str, Any] | None, metric_b: dict[str, Any] | None) -> dict[str, Any]:
    """Explain whether two observations share indicator, unit, period and observation year."""
    if not metric_a or not metric_b:
        return {"comparable": False, "reason": "至少一条路径没有可用的同类指标数据。"}
    if metric_a.get("indicator_code") != metric_b.get("indicator_code"):
        return {"comparable": False, "reason": "行业分类或指标代码不同，不能直接并排比较。"}
    if metric_a.get("unit") != metric_b.get("unit"):
        return {"comparable": False, "reason": "单位不同，不能直接比较。"}
    if (metric_a.get("period_start"), metric_a.get("period_end")) != (
        metric_b.get("period_start"),
        metric_b.get("period_end"),
    ):
        return {"comparable": False, "reason": "选择的统计时间范围不同，不能直接比较。"}
    if metric_a.get("observation_year") != metric_b.get("observation_year"):
        return {"comparable": False, "reason": "两侧最新观测年份不同，不能直接比较。"}
    countries_differ = metric_a.get("country_code") != metric_b.get("country_code")
    reason = (
        "指标代码、单位、选择范围和最新观测年份一致，可作跨国国家级宏观对照；"
        "地区不同，不能据此推断本地岗位或个人机会。"
        if countries_differ
        else "指标代码、单位、选择范围和最新观测年份一致，可按国家级行业口径对照。"
    )
    return {
        "comparable": True,
        "geography_differs": countries_differ,
        "comparison_level": "cross_country_macro" if countries_differ else "same_country_macro",
        "reason": reason,
    }


def fetch_comparison_evidence(market_scope: Any, *, now: datetime | None = None) -> dict[str, Any]:
    """Fetch optional public market evidence without accepting or forwarding path text."""
    if not isinstance(market_scope, dict) or market_scope.get("enabled") is not True:
        return {
            "status": "disabled",
            "message": "未启用行业市场查询；本次分析只使用本地评分。",
            "paths": [],
            "comparability": [],
        }

    submitted_paths = market_scope.get("paths")
    if not isinstance(submitted_paths, dict):
        submitted_paths = {}
    scopes = {path_id: submitted_paths.get(path_id) for path_id in ("A", "B")}
    query_scopes = {path_id: _validated_query_scope(scopes[path_id]) for path_id in ("A", "B")}
    if any(scope is None for scope in query_scopes.values()):
        return {
            "status": "incomplete_scope",
            "message": "请为路径 A、B 分别选择国家、行业和有效年度范围后再查询；未发送外部请求。",
            "paths": [
                {
                    "id": path_id,
                    "status": "incomplete_scope",
                    "country_code": scope.get("country_code", "") if isinstance(scope, dict) else "",
                    "industry_code": scope.get("industry_code", "") if isinstance(scope, dict) else "",
                    "metrics": [],
                }
                for path_id, scope in scopes.items()
                if path_id in ("A", "B")
            ],
            "comparability": [],
        }

    paths = [
        _path_evidence(path_id, scopes[path_id], query_scopes[path_id], now=now)
        for path_id in ("A", "B")
    ]
    metrics_a = {metric["key"]: metric for metric in paths[0]["metrics"]}
    metrics_b = {metric["key"]: metric for metric in paths[1]["metrics"]}
    comparability = []
    for metric_key in ("value_added_share", "annual_growth"):
        result = assess_metric_comparability(metrics_a.get(metric_key), metrics_b.get(metric_key))
        result["metric_key"] = metric_key
        result["label"] = (metrics_a.get(metric_key) or metrics_b.get(metric_key) or {}).get(
            "name", "对应行业指标"
        )
        comparability.append(result)

    statuses = {path["status"] for path in paths}
    if statuses == {"available"}:
        status = "available"
        message = "已取得国家级年度行业背景数据；这些指标独立展示，不会改变当前条件匹配分。"
    elif statuses == {"stale"}:
        status = "stale"
        message = "已有指标数据，但最新观测年份较旧；请在来源页面核对更新情况。"
    elif statuses == {"rate_limited"}:
        status = "rate_limited"
        message = "数据源暂时限流；请稍后重试，本地评分仍已完成。"
    elif statuses == {"no_data"}:
        status = "no_data"
        message = "所选国家、行业或时间范围暂无可用指标；本地评分仍已完成。"
    elif "available" in statuses or "partial" in statuses or "stale" in statuses:
        status = "partial"
        message = "部分路径或指标有数据；缺失和过期状态已单独标出，不补值、不推测。"
    elif "rate_limited" in statuses:
        status = "rate_limited"
        message = "数据源暂时限流；请稍后重试，本地评分仍已完成。"
    else:
        status = "unavailable"
        message = "市场数据源暂时不可用或返回格式异常；本地评分仍已完成。"
    return {
        "status": status,
        "message": message,
        "paths": paths,
        "comparability": comparability,
        "source_name": SOURCE_NAME,
        "source_documentation": API_DOCUMENTATION,
        "license": "CC BY 4.0",
        "license_url": LICENSE_URL,
        "retrieved_at": next((path["retrieved_at"] for path in paths if path["retrieved_at"]), None),
        "granularity": "国家级 · 年度 · 行业增加值",
        "limitation": LIMITATION,
    }
