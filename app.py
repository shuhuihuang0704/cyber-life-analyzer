"""Cyber Life Analyzer — Flask application entry point."""

from flask import Flask, jsonify, render_template, request

from analyzer import AnalysisInputError, analyze_paths

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
    return jsonify(result)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
