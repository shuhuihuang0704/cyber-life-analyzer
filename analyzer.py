"""Deterministic, explainable trend simulation used in place of a live LLM."""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any


class AnalysisInputError(ValueError):
    """Raised when an analysis request is incomplete or malformed."""


def _text(value: Any, label: str, limit: int = 80) -> str:
    if not isinstance(value, str):
        raise AnalysisInputError(f"{label}需要填写文字。")
    cleaned = re.sub(r"\s+", " ", value).strip()
    if not cleaned:
        raise AnalysisInputError(f"{label}不能为空。")
    if len(cleaned) > limit:
        raise AnalysisInputError(f"{label}请控制在 {limit} 个字符以内。")
    return cleaned


def _number(value: Any, label: str, low: int = 1, high: int = 5) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or int(value) != value:
        raise AnalysisInputError(f"{label}格式不正确。")
    number = int(value)
    if not low <= number <= high:
        raise AnalysisInputError(f"{label}需在 {low} 到 {high} 之间。")
    return number


def analyze_paths(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a structured comparative three-year scenario simulation."""
    option_a = _text(payload.get("option_a"), "路径 A")
    option_b = _text(payload.get("option_b"), "路径 B")
    context = _text(payload.get("context", "暂未补充背景"), "背景", 300)
    risk_tolerance = _number(payload.get("risk_tolerance", 3), "风险偏好")
    resources = _number(payload.get("resources", 3), "资源储备")
    urgency = _number(payload.get("urgency", 3), "行动紧迫度")

    seed_text = "|".join((option_a, option_b, context))
    seed = int(hashlib.sha256(seed_text.encode("utf-8")).hexdigest()[:8], 16)
    jitter = ((seed % 17) - 8) / 10
    risk_gap = risk_tolerance - 3
    resource_gap = resources - 3
    urgency_gap = urgency - 3

    # These are heuristic scenario scores, not probabilities or predictions.
    score_a = 50 + jitter + risk_gap * 4 + resource_gap * 2 - urgency_gap
    score_b = 50 - jitter - risk_gap * 4 - resource_gap * 2 + urgency_gap
    score_a = max(28, min(72, round(score_a)))
    score_b = 100 - score_a
    preferred = "A" if score_a >= score_b else "B"
    preferred_label = option_a if preferred == "A" else option_b
    alternate_label = option_b if preferred == "A" else option_a
    confidence = "温和倾向" if abs(score_a - score_b) < 12 else "较清晰倾向"

    paths = []
    for key, label, score, polarity in (
        ("A", option_a, score_a, 1), ("B", option_b, score_b, -1)
    ):
        baseline = 48 + (score - 50) * 0.55
        momentum = polarity * (risk_gap * 1.2 + resource_gap * 0.8)
        energy = []
        for year in range(1, 4):
            value = round(max(20, min(85, baseline + momentum * year + math.sin(seed % 7 + year) * 5)))
            energy.append({"year": year, "value": value})
        paths.append({"id": key, "label": label, "fit_score": score, "energy": energy})

    phases = [
        {"year": "第 1 年", "title": "试探与校准", "description": f"先用低成本行动验证「{preferred_label}」的关键假设，避免一次性押注。", "tone": "signal"},
        {"year": "第 2 年", "title": "积累与分化", "description": "能力、关系与资源的复利开始显现；根据实际反馈调整投入比例。", "tone": "steady"},
        {"year": "第 3 年", "title": "收敛与选择", "description": f"若早期指标持续改善，可加码「{preferred_label}」；否则保留切换到「{alternate_label}」的余地。", "tone": "caution"},
    ]
    opportunities = [
        {"window": "0–6 个月", "title": "低成本试运行", "detail": "通过短项目、访谈或影子体验，快速获得一手信息。", "kind": "opportunity"},
        {"window": "6–18 个月", "title": "能力复利窗口", "detail": "将新经验沉淀为作品、技能或可迁移资源。", "kind": "opportunity"},
        {"window": "18–30 个月", "title": "机会成本检查点", "detail": "复盘投入产出与身心状态，避免惯性投入替代真实选择。", "kind": "risk"},
    ]
    trend = (
        f"从你提供的背景和偏好看，「{preferred_label}」目前呈现出略占优势的趋势，"
        f"属于{confidence}。未来三年更像是先验证、再积累、后收敛的过程；"
        "分析结果会随现实条件和行动反馈变化。"
    )
    advice = (
        f"当前可以优先探索「{preferred_label}」，但建议把它设计成一个可撤回的阶段性实验："
        "先定义 90 天验证指标、预算和退出条件，再决定是否扩大投入。"
    )
    return {
        "meta": {"engine": "heuristic-llm-simulation", "version": "1.0",
                 "scenario_id": hashlib.sha256(seed_text.encode("utf-8")).hexdigest()[:12]},
        "input": {"option_a": option_a, "option_b": option_b, "context": context,
                  "risk_tolerance": risk_tolerance, "resources": resources, "urgency": urgency},
        "trend_analysis": {"summary": trend, "confidence": confidence,
                           "drivers": ["风险承受偏好", "可用资源储备", "行动时间压力"],
                           "caveat": "这是基于有限输入的情景模拟，不代表确定的未来，也不构成专业建议。"},
        "paths": paths,
        "phases": phases,
        "decision_points": opportunities,
        "recommendation": {"preferred_path": preferred, "preferred_label": preferred_label,
                           "score_a": score_a, "score_b": score_b, "summary": advice,
                           "next_step": "写下一个 90 天内可观察、可复盘的验证指标。"},
    }
