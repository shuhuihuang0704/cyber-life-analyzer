# 赛博人生分析器

> 把人生的岔路口，变成可读的信号。

一个基于 **Flask + 原生 HTML / CSS / JavaScript** 构建的个人决策推演网页。输入两种备选路径与当前状态，即可查看未来三年的趋势模拟、阶段变化、风险与机遇，以及一份可执行的倾向性建议。

分析结果用于帮助梳理思路，不是对未来的确定预测。

## 功能亮点

- **双路径对比**：同时评估两种选择，查看趋势匹配度与能量变化曲线。
- **三年阶段推演**：按年度呈现试探、积累到收敛的可能路径。
- **风险与机遇节点**：标出值得验证的时间窗口和决策检查点。
- **可调整的现实变量**：结合背景描述、风险偏好、资源储备与行动紧迫度。
- **响应式界面**：适配桌面和手机浏览器。
- **开箱即用**：无需数据库、外部服务或 API Key。

## 快速开始

需要 **Python 3.9+** 和 `pip`。

### macOS / Linux

```bash
git clone https://github.com/shuhuihuang0704/cyber-life-analyzer.git
cd cyber-life-analyzer

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

### Windows（PowerShell）

```powershell
git clone https://github.com/shuhuihuang0704/cyber-life-analyzer.git
cd cyber-life-analyzer

py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

启动后访问：

<http://127.0.0.1:5000>

停止服务时，在终端按 `Ctrl + C`。

## 使用方式

填写路径 A、路径 B 和当前背景，再调整风险偏好、资源储备及行动紧迫度，点击「生成趋势推演」。

示例：

- 路径 A：换一份更有成长空间的工作
- 路径 B：留在当前岗位继续积累
- 当前背景：工作稳定，但成长空间有限；希望平衡收入与长期发展

## 分析逻辑说明

当前版本使用**可重复的启发式模拟逻辑**生成趋势分数、三年能量曲线和建议，不会调用外部 LLM，也不会把分数解释为成功概率。相同输入会得到一致的推演结果。

项目预留了结构化分析结果，后续可在 `analyzer.py` 中接入真实 LLM，同时保留现有前端输出结构。

> 本工具只用于自我探索与讨论，不构成确定预测，也不替代医疗、法律、财务或其他专业建议。请结合现实信息独立判断重要决定。

## API

### `POST /api/analyze`

请求头：`Content-Type: application/json`

```json
{
  "option_a": "换工作",
  "option_b": "留在现状",
  "context": "目前工作稳定，但成长空间有限",
  "risk_tolerance": 3,
  "resources": 3,
  "urgency": 3
}
```

三个数值字段范围均为 **1–5**。成功时返回趋势分析、两条路径、阶段推演、风险与机遇节点及建议；输入不合法时返回 HTTP 400 和错误说明。

## 项目结构

```text
cyber-life-analyzer/
├── app.py                 # Flask 应用与 API 路由
├── analyzer.py            # 趋势模拟与输入校验
├── requirements.txt       # Python 依赖
├── templates/
│   └── index.html         # 页面结构
└── static/
    ├── app.js             # 表单交互、结果渲染与曲线绘制
    └── style.css          # 页面样式与响应式布局
```

## 技术栈

- 前端：HTML、CSS、原生 JavaScript、Canvas
- 后端：Python、Flask
- 分析：可解释的启发式趋势模拟（当前不调用外部 LLM）

欢迎提交 Issue 或 Pull Request，一起改进这个小工具。