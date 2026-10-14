"""Transparent, deterministic decision comparison using user-provided ratings."""

from __future__ import annotations

import math
import re
from typing import Any


class AnalysisInputError(ValueError):
    """Raised when an analysis request is incomplete or malformed."""


FACTORS = (
    {"key": "growth", "label": "成长空间", "high_is_better": True},
    {"key": "stability", "label": "稳定性", "high_is_better": True},
    {"key": "cost", "label": "成本负担", "high_is_better": False},
    {"key": "reversibility", "label": "可逆性", "high_is_better": True},
)
FACTOR_BY_KEY = {factor["key"]: factor for factor in FACTORS}
BALANCED_THRESHOLD = 6
PREFERENCE_LABELS = {
    "risk_tolerance": "风险偏好",
    "resources": "资源储备",
    "urgency": "行动紧迫度",
}


def _utf16_length(value: str) -> int:
    """Match HTML maxlength, which counts UTF-16 code units."""
    return len(value.encode("utf-16-le", errors="surrogatepass")) // 2


def _text(value: Any, label: str, limit: int = 80) -> str:
    if not isinstance(value, str):
        raise AnalysisInputError(f"{label}需要填写文字。")
    if _utf16_length(value) > limit:
        raise AnalysisInputError(f"{label}请控制在 {limit} 个字符以内。")
    cleaned = re.sub(r"\s+", " ", value).strip()
    if not cleaned:
        raise AnalysisInputError(f"{label} 不能为空。")
    return cleaned


def _optional_text(value: Any, label: str, limit: int = 300) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise AnalysisInputError(f"{label}格式不正确，请填写文字。")
    if _utf16_length(value) > limit:
        raise AnalysisInputError(f"{label}请控制在 {limit} 个字符以内。")
    cleaned = re.sub(r"\s+", " ", value).strip()
    return cleaned


def _number(value: Any, label: str, low: int = 1, high: int = 5) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or (isinstance(value, float) and not math.isfinite(value))
        or int(value) != value
    ):
        raise AnalysisInputError(f"{label}请填写 {low} 到 {high} 的整数。")
    number = int(value)
    if not low <= number <= high:
        raise AnalysisInputError(f"{label}需在 {low} 到 {high} 之间。")
    return number


def _read_path_ratings(value: Any) -> dict[str, dict[str, int]]:
    if not isinstance(value, dict):
        raise AnalysisInputError("请分别为路径 A 和路径 B 完成四项 1–5 分自评。")

    ratings: dict[str, dict[str, int]] = {}
    for path_id in ("A", "B"):
        path_values = value.get(path_id)
        if not isinstance(path_values, dict):
            raise AnalysisInputError(f"请完成路径 {path_id} 的四项自评。")
        ratings[path_id] = {}
        for factor in FACTORS:
            key = factor["key"]
            label = factor["label"]
            if key not in path_values:
                raise AnalysisInputError(f"请为路径 {path_id} 评估{label}（1–5 分）。")
            ratings[path_id][key] = _number(path_values[key], f"路径 {path_id} 的{label}")
    return ratings


def _calculate_weights(risk_tolerance: int, resources: int, urgency: int) -> dict[str, int]:
    """Return percentage weights from the 30/25/25/20 baseline.

    Each risk point shifts 4 percentage points between stability and growth.
    Each resource point below 3 shifts 2 points from growth to cost; above 3 reverses it.
    Each urgency point above 3 shifts 2 points from reversibility to cost; below 3 reverses it.
    Every adjustment sums to zero, so weights remain at 100 percent.
    """
    risk_shift = (risk_tolerance - 3) * 4
    resource_shift = (3 - resources) * 2
    urgency_shift = (urgency - 3) * 2
    return {
        "growth": 30 + risk_shift - resource_shift,
        "stability": 25 - risk_shift,
        "cost": 25 + resource_shift + urgency_shift,
        "reversibility": 20 - urgency_shift,
    }


def _score_path(path_id: str, label: str, ratings: dict[str, int], weights: dict[str, int]) -> dict[str, Any]:
    breakdown = []
    for factor in FACTORS:
        key = factor["key"]
        rating = ratings[key]
        # Higher cost is less favorable; the other dimensions score higher when rated higher.
        favorable_rating = rating if factor["high_is_better"] else 6 - rating
        normalized_score = (favorable_rating - 1) * 25
        weight = weights[key]
        breakdown.append(
            {
                "key": key,
                "label": factor["label"],
                "rating": rating,
                "normalized_score": normalized_score,
                "weight": weight,
                "contribution": round(normalized_score * weight / 100, 2),
            }
        )

    return {
        "id": path_id,
        "label": label,
        "fit_score": round(sum(item["contribution"] for item in breakdown), 1),
        "ratings": ratings,
        "breakdown": breakdown,
    }


def _leader_for_preferences(
    path_ratings: dict[str, dict[str, int]],
    risk_tolerance: int,
    resources: int,
    urgency: int,
) -> str | None:
    weights = _calculate_weights(risk_tolerance, resources, urgency)
    scores = {
        path_id: _score_path(path_id, "", ratings, weights)["fit_score"]
        for path_id, ratings in path_ratings.items()
    }
    if abs(scores["A"] - scores["B"]) < BALANCED_THRESHOLD:
        return None
    return "A" if scores["A"] > scores["B"] else "B"


def _sensitivity_check(
    path_ratings: dict[str, dict[str, int]],
    preferences: dict[str, int],
    current_leader: str | None,
) -> dict[str, Any]:
    """Re-score each preference one point below and above its current value."""
    checks = []
    changed_preferences = []
    for key, label in PREFERENCE_LABELS.items():
        current = preferences[key]
        low_value = max(1, current - 1)
        high_value = min(5, current + 1)
        low_values = dict(preferences, **{key: low_value})
        high_values = dict(preferences, **{key: high_value})
        low_leader = _leader_for_preferences(path_ratings, **low_values)
        high_leader = _leader_for_preferences(path_ratings, **high_values)
        changed = low_leader != current_leader or high_leader != current_leader
        if changed:
            changed_preferences.append(key)
        checks.append(
            {
                "key": key,
                "label": label,
                "current": current,
                "lower_value": low_value,
                "lower_leader": low_leader,
                "upper_value": high_value,
                "upper_leader": high_leader,
                "changes_leader": changed,
            }
        )

    is_sensitive = bool(changed_preferences)
    if is_sensitive:
        labels = "、".join(PREFERENCE_LABELS[key] for key in changed_preferences)
        summary = f"结果对偏好设置敏感：将{labels}上下调整 1 档会改变领先关系。此项只检查排序稳定性，不代表概率。"
    else:
        summary = "在各项偏好分别上下调整 1 档时，领先关系未改变；这不代表评分或未来结果有把握。"
    return {
        "status": "sensitive" if is_sensitive else "stable",
        "changed_preferences": changed_preferences,
        "checks": checks,
        "summary": summary,
    }


def _action_for_factor(
    factor_key: str,
    label: str,
    preferred_path: str | None,
    weak_dimension: bool = False,
) -> dict[str, str]:
    experiments = {
        "growth": (
            f"用 90 天完成一项与「{label}」相关、可展示的最小成果，例如一个小项目或试用任务。",
            "交付 1 项成果，并收集至少 2 位相关人士的具体反馈。",
        ),
        "stability": (
            f"在 90 天内核实「{label}」的收入、保障或工作节奏假设，并整理至少 2 种备用安排。",
            "记录 3 项可核验的稳定性证据，并标明哪些假设仍未确认。",
        ),
        "cost": (
            f"围绕「{label}」做不超过 90 天的小规模试行；开始前写下可接受的月度现金支出和每周时间上限。",
            "每周记录现金支出和时间投入，并与事先写下的上限比较。",
        ),
        "reversibility": (
            f"先为「{label}」写下退出步骤，再做一个 90 天内可撤回的小试验。",
            "记录回到另一条路径需要的步骤、时间和成本，确认退出方案仍可执行。",
        ),
    }
    experiment, metric = experiments[factor_key]

    if preferred_path:
        if factor_key == "cost" and weak_dimension:
            continue_if = "第 90 天复评时，成本负担评分至少降低 1 分，且这条路径仍领先至少 6 分。"
            pause_if = "若成本负担仍为 4–5 分且时间或现金投入超出预设上限，暂停扩大投入。"
        elif factor_key == "cost":
            continue_if = "第 90 天复评时，成本负担保持在 1–2 分，且这条路径仍领先至少 6 分。"
            pause_if = "若成本负担升到 4–5 分，或时间/现金投入超出预设上限，暂停扩大投入。"
        elif weak_dimension:
            continue_if = "第 90 天重新评分时，本次关注的维度至少提高 1 分，且这条路径仍领先至少 6 分。"
            pause_if = "若该维度仍为 1–2 分且关键假设没有新证据，暂停扩大投入并重新比较。"
        else:
            continue_if = "第 90 天重新评分时，本次关注的维度没有下降，且这条路径仍领先至少 6 分。"
            pause_if = "若该维度降到 2 分及以下，或关键假设无法验证，暂停扩大投入并重新比较。"
    else:
        experiment = f"在 90 天内围绕两条路径的「{label}」各做一次同口径的小验证，避免只凭印象比较。"
        metric = "为 A、B 各记录至少 1 项可核验数据，并在获得证据后更新对应的 1–5 分自评。"
        continue_if = "仅在获得新证据后扩大试验；第 90 天重新评分，分差达到 6 分再考虑优先投入。"
        pause_if = "若没有获得新证据，或实际投入超过事先写下的上限，停止扩大试验并保留两条路径。"

    return {
        "experiment": experiment,
        "metric": metric,
        "continue_if": continue_if,
        "pause_if": pause_if,
    }


def _checkpoint_question(factor_key: str) -> str:
    questions = {
        "growth": "这条路径是否带来了新的技能、责任或可展示成果？有哪些具体证据？",
        "stability": "收入、保障和日常节奏的关键假设，哪些已核实，哪些仍不确定？",
        "cost": "实际的现金支出和时间投入是否仍在事先设定的上限内？",
        "reversibility": "如果现在暂停，回到另一条路径需要哪些步骤、时间和成本？",
    }
    return questions[factor_key]


def analyze_paths(payload: dict[str, Any]) -> dict[str, Any]:
    """Compare two options using only explicit 1–5 ratings and preference weights."""
    option_a = _text(payload.get("option_a"), "路径 A")
    option_b = _text(payload.get("option_b"), "路径 B")
    context = _optional_text(payload.get("context", ""), "背景", 300)
    risk_tolerance = _number(payload.get("risk_tolerance", 3), "风险偏好")
    resources = _number(payload.get("resources", 3), "资源储备")
    urgency = _number(payload.get("urgency", 3), "行动紧迫度")
    path_ratings = _read_path_ratings(payload.get("path_ratings"))

    weights = _calculate_weights(risk_tolerance, resources, urgency)
    paths = [
        _score_path("A", option_a, path_ratings["A"], weights),
        _score_path("B", option_b, path_ratings["B"], weights),
    ]
    path_a, path_b = paths
    score_gap = round(abs(path_a["fit_score"] - path_b["fit_score"]), 1)
    is_balanced = score_gap < BALANCED_THRESHOLD
    preferred = None if is_balanced else (path_a if path_a["fit_score"] > path_b["fit_score"] else path_b)
    preferences = {
        "risk_tolerance": risk_tolerance,
        "resources": resources,
        "urgency": urgency,
    }
    sensitivity = _sensitivity_check(path_ratings, preferences, preferred["id"] if preferred else None)

    if preferred:
        weakest = min(preferred["breakdown"], key=lambda item: item["normalized_score"])
        focus_key = weakest["key"]
        focus_label = weakest["label"]
        summary = (
            f"「{preferred['label']}」在当前输入和权重下高出 {score_gap:.1f} 分。"
            f"这只是条件匹配结果，不是成功概率；建议先验证「{focus_label}」相关假设。"
        )
        action = _action_for_factor(
            focus_key,
            preferred["label"],
            preferred["id"],
            weak_dimension=weakest["normalized_score"] < 50,
        )
        recommendation_title = f"当前较适配：{preferred['label']}"
    else:
        differences = {
            factor["key"]: abs(path_ratings["A"][factor["key"]] - path_ratings["B"][factor["key"]]) * weights[factor["key"]]
            for factor in FACTORS
        }
        focus_key = max(differences, key=differences.get)
        if differences[focus_key] == 0:
            focus_key = max(weights, key=weights.get)
        focus_label = FACTOR_BY_KEY[focus_key]["label"]
        summary = (
            f"两条路径当前只相差 {score_gap:.1f} 分，暂时不指定优先项。"
            f"先收集「{focus_label}」的真实证据，再重新评分。"
        )
        action = _action_for_factor(focus_key, focus_label, None)
        recommendation_title = "两条路径当前接近"

    checkpoints = [
        {
            "window": "第 30 天",
            "title": f"核实{focus_label}",
            "question": _checkpoint_question(focus_key),
        },
        {
            "window": "第 60 天",
            "title": "检查实际投入",
            "question": "记录现金支出和时间投入；它们是否仍符合你当前的资源储备与行动紧迫度？",
        },
        {
            "window": "第 90 天",
            "title": "重新比较",
            "question": f"用同一套四项评分重新评估两条路径。当前分差为 {score_gap:.1f} 分；是否出现了足以改变评分的新证据？",
        },
    ]

    return {
        "meta": {"engine": "transparent-weighted-score", "version": "2.1"},
        "input": {
            "option_a": option_a,
            "option_b": option_b,
            "context": context,
            "risk_tolerance": risk_tolerance,
            "resources": resources,
            "urgency": urgency,
            "path_ratings": path_ratings,
        },
        "scoring": {
            "base_weights": {"growth": 30, "stability": 25, "cost": 25, "reversibility": 20},
            "weights": weights,
            "balanced_threshold": BALANCED_THRESHOLD,
            "formula": "各项效用分 × 权重后求和；成长、稳定、可逆性高分更优，成本负担反向计分。",
            "weight_rules": [
                "风险偏好每升 1 分，成长空间权重 +4%，稳定性权重 −4%。",
                "资源储备每降 1 分，成长空间权重 −2%，成本负担权重 +2%。",
                "行动紧迫度每升 1 分，成本负担权重 +2%，可逆性权重 −2%。",
            ],
        },
        "comparison": {
            "status": "balanced" if is_balanced else f"lean_{preferred['id'].lower()}",
            "score_gap": score_gap,
            "focus_dimension": {"key": focus_key, "label": focus_label},
            "summary": summary,
        },
        "sensitivity": sensitivity,
        "paths": paths,
        "checkpoints": checkpoints,
        "recommendation": {
            "preferred_path": preferred["id"] if preferred else None,
            "preferred_label": preferred["label"] if preferred else None,
            "title": recommendation_title,
            "summary": summary,
            **action,
        },
        "caveat": (
            "结果只整理你填写的自评分和偏好权重，不会理解背景备注，也不代表未来概率。"
            "分数用于比较当前判断；重要决定请结合可核验信息和现实约束。"
        ),
    }
