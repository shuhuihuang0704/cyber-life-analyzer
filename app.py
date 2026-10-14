"""Cyber Life Analyzer — Flask application entry point."""

from flask import Flask, jsonify, render_template, request

from analyzer import AnalysisInputError, analyze_paths
from market_data import fetch_comparison_evidence

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/analyze")
def analyze():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "请提交有效的 JSON 请求。"}), 400
    try:
        result = analyze_paths(payload)
    except AnalysisInputError as exc:
        return jsonify({"error": str(exc)}), 400
    # The public-data provider receives only this explicit structured scope, never path labels,
    # background notes, self-ratings or the local comparison/recommendation result.
    try:
        result["market_evidence"] = fetch_comparison_evidence(payload.get("market_scope"))
    except Exception:
        # Optional network data must never block the independent local scoring result.
        result["market_evidence"] = {
            "status": "unavailable",
            "message": "市场数据暂时不可用；本地评分仍已完成。",
            "paths": [],
            "comparability": [],
        }
    return jsonify(result)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
