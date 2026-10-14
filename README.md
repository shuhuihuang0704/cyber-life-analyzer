# 赛博人生分析器

使用原生 HTML / CSS / JavaScript 与 Python Flask 的本地网页项目。填写两条人生路径和当前状态后，生成三年趋势模拟、路径能量曲线、阶段推演、风险与机遇节点及倾向性建议。

## 运行环境

- Python 3.9+
- pip

## 启动

```bash
python -m venv .venv
source .venv/bin/activate       # Windows：.venv\\Scripts\\activate
pip install -r requirements.txt
python app.py
```

打开 <http://127.0.0.1:5000>。

## 当前分析逻辑

当前版本使用可重复的启发式模拟逻辑，不调用外部 LLM，也不需要 API 密钥。结果仅用于自我探索与讨论，不构成确定预测或专业建议。