# 赛博人生分析器

> 把人生的岔路口，拆成可以核对的条件。

一个基于 **Flask + 原生 HTML / CSS / JavaScript** 的本地决策比较工具。给两条可能路径做同一套自评，查看权重、得分明细和 90 天内可验证的下一步。

评分只整理用户自评，不是成功概率或未来预测。背景备注只供回看，不参与评分，也不会保存。

## 功能

- **双路径对照**：比较成长空间、稳定性、成本负担和可逆性。
- **透明权重**：风险偏好、资源储备和行动紧迫度按页面公布的规则调整权重。
- **差距提示**：两条路径的总分差小于 6 分时，不指定优先路径。
- **90 天行动**：按当前得分较弱或最需要补充证据的维度，提供实验、观察指标和复盘条件。
- **可选市场证据**：明确选择查询后，通过 Flask 服务端访问世界银行公开的国家级年度行业指标；不需要 API Key。未勾选时完全离线完成评分。
- **评分敏感性**：分别将风险偏好、资源储备、行动紧迫度上下调整 1 档，检查当前领先关系是否改变。
- **隐私边界**：不使用数据库、登录或 LLM；不保存用户输入。外部请求只发送所选国家代码、由行业选择映射出的 WDI 指标代码和年份范围。
- **响应式界面**：适配桌面和窄屏，并支持键盘调整评分。

## 快速开始

需要 **Python 3.10+** 和 `pip`。

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

启动后访问 <http://127.0.0.1:5000>。停止服务时，在终端按 `Ctrl + C`。

## 使用方式

1. 填写路径 A 和路径 B，也可以点击「加载示例」查看输入方式。
2. 按相同标准给两条路径的四项条件各打 1–5 分。成本负担方向相反：1 分代表低成本，5 分代表高成本。
3. 调整风险偏好、资源储备和行动紧迫度。
4. 查看总分、权重、各项得分贡献以及 30、60、90 天复盘问题。
5. 若比较的是职业或行业路径，可选中「查询公开国家级行业统计」，为 A、B 分别选择国家、行业和年份。可用“复制路径 A 到路径 B”快速设置。
6. 查看独立的市场证据及来源详情；选择一项 90 天内可验证的小实验，并提前写下继续或暂停条件。

背景备注是可选项，会随本次 API 响应返回，但不参与评分，也不会保存到本地。市场查询默认关闭；未勾选或 A、B 查询范围不完整时不会发出外部请求。离线、超时、限流或数据缺失时，本地评分仍会完成。

## 行业市场证据

第一版只接入 **世界银行 World Development Indicators (WDI) Indicators API v2**。API 文档称其提供公开指标序列，且访问不需要 API Key；本工具只查询下列国家级年度宏观行业指标：

| 用户选择 | 增加值占 GDP | 增加值年度增速 | 单位 |
| --- | --- | --- | --- |
| 农业、林业和渔业 | NV.AGR.TOTL.ZS | NV.AGR.TOTL.KD.ZG | % of GDP；annual % growth |
| 工业（含建筑业） | NV.IND.TOTL.ZS | NV.IND.TOTL.KD.ZG | % of GDP；annual % growth |
| 制造业 | NV.IND.MANF.ZS | NV.IND.MANF.KD.ZG | % of GDP；annual % growth |
| 服务业 | NV.SRV.TOTL.ZS | NV.SRV.TOTL.KD.ZG | % of GDP；annual % growth |

接口按用户选择的国家代码、WDI 行业指标和年份范围查询。页面展示观测值年份、抓取时间、年度更新口径、来源链接、指标代码及 CC BY 4.0 许可。WDI API 没有提供每条观测的发布日期，因此界面会明确显示“源接口未提供单项发布日期”，不会把观测年份冒充发布日期。距当前超过两年的最新观测会标为“数据年份较旧”。公开数据只在进程内缓存 6 小时，不缓存任何用户输入。

这些值来自国家统计机构、国民账户资料及世界银行估算，属于国家级、年度的**行业增加值背景**。它们不是岗位需求、招聘职位数量、职业薪资或个人收入，也不能代表某个城市。若用户填写城市、职业代码或资历，这些字段只在本地结果中注明，当前数据接口不会查询或发送它们。两个指标只有在指标代码、单位、所选年份范围和最新观测年份一致时才标为可比；行业分类、时间范围或观测年份不同会提示不可直接比较。即使国家级宏观指标可作跨国对照，也不代表两地岗位市场相同。

市场证据仅用于核对假设，始终与主观自评分开显示，不转换成分数或概率，不改变 0–100 的当前条件匹配分或“小于 6 分不指定赢家”的规则。

### 数据源覆盖与未接入范围

- **中国国家统计局“国家数据”**提供国家、地区、行业等统计数据入口；人社部发布统计公报。当前版本没有接入这些门户的未文档化内部接口，也没有找到可直接用于本工具、明确允许程序调用且范围稳定的全国岗位级招聘 API。中国选择目前只能得到世界银行国家级 WDI 行业宏观指标；城市、岗位和职业数据暂不支持实时查询。
- **中国城市开放数据平台**由各地分别维护，数据格式、申请流程、许可和 API 能力各异。后续只有在目录明确公开、接口文档和使用许可清楚时才会单独接入；不会抓取招聘网站或绕过登录、验证码。
- **美国 BLS Public Data API**有官方接口文档；V1 无需注册，但未注册用户上限为每天 25 次请求、每次 25 条序列、最多 10 年，且不返回序列元数据；V2 需注册，限制更高。BLS 发布的公开内容可复用但应注明来源。当前版本未接入 BLS。
- **Eurostat**提供公开 Statistics REST API 及 SDMX 2.1 / 3.0 接口，可按数据集维度查询；更新频率由各数据集元数据确定。数据一般可商用复用并注明来源，但部分第三方数据和非欧盟来源数据有例外。当前版本未接入欧盟数据。
- 世界银行指标只能作为国家级宏观行业背景，不能标成岗位级招聘或薪资数据。

接口核对来源：[World Bank Indicators API 文档](https://datahelpdesk.worldbank.org/knowledgebase/articles/889392-about-the-indicators-api-documentation)、[WDI 制造业增加值占比](https://data.worldbank.org/indicator/NV.IND.MANF.ZS)、[WDI 制造业年度增速](https://data.worldbank.org/indicator/NV.IND.MANF.KD.ZG)、[World Bank 数据许可](https://creativecommons.org/licenses/by/4.0/)、[国家统计局“国家数据”](https://data.stats.gov.cn/)、[人社部统计公报目录](https://www.mohrss.gov.cn/SYrlzyhshbzb/zwgk/szrs/tjgb/index.html)、[BLS API 文档](https://www.bls.gov/developers/home.htm)、[BLS FAQ 与配额](https://www.bls.gov/developers/api_FAQs.htm)、[BLS 使用条款](https://www.bls.gov/developers/termsOfService.htm)、[Eurostat API 文档](https://ec.europa.eu/eurostat/web/user-guides/data-browser/api-data-access/api-introduction)、[Eurostat 数据许可与复用](https://ec.europa.eu/eurostat/help/copyright-notice)、[Eurostat 更新与发布说明](https://ec.europa.eu/eurostat/about-us/communicating-disseminating-statistics)。

### 网络请求和隐私

外部请求由 Flask 服务端发出，设置 5 秒超时和最多 1 次重试；HTTP 429 会单独显示为限流状态。请求 URL 只包含经白名单校验的国家代码、固定 WDI 指标代码和年份范围。路径名称、背景备注、偏好、自评分数、推荐结果、城市、职业代码和经验范围不会发往世界银行。请求异常、格式错误、无数据或过期数据都显示具体状态，不插值、不用默认数值。查询关闭时，API 不访问外部数据源；本地分析不依赖网络。

世界银行数据按其 [CC BY 4.0 许可](https://creativecommons.org/licenses/by/4.0/)使用，界面保留来源与许可链接。此许可说明仅适用于世界银行数据，不代表其他门户采用同一许可。

## 评分机制与限制

每项自评为 1–5 分。成长空间、稳定性和可逆性按高分更有利计算；成本负担反向计算。效用分按 `1 分 → 0`、`5 分 → 100` 线性换算。路径总分为四项效用分乘以各自权重后求和，范围为 0–100。

权重从成长空间 30%、稳定性 25%、成本负担 25%、可逆性 20% 开始，并按以下规则调整；四项权重始终合计 100%。

- 风险偏好每提高 1 分，成长空间权重增加 4 个百分点，稳定性权重减少 4 个百分点。
- 资源储备每降低 1 分，成本负担权重增加 2 个百分点，成长空间权重减少 2 个百分点。
- 行动紧迫度每提高 1 分，成本负担权重增加 2 个百分点，可逆性权重减少 2 个百分点。

两条路径差距小于 6 分时，结果标记为「当前接近」，不指定赢家。评分只表达用户当前自评和偏好权重之间的匹配程度；工具不会理解背景备注，也不能验证用户评分是否准确。应结合现实数据和实际体验独立判断重要决定。本工具不替代医疗、法律、财务或其他专业建议。

偏好敏感性检查会分别对三项偏好上下调整一档，再用原公式重算。若领先关系改变，界面会指出对应偏好；这是排序稳定性检查，不是成功概率、统计置信度或对未来的预测。

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
  "urgency": 3,
  "path_ratings": {
    "A": {"growth": 5, "stability": 2, "cost": 4, "reversibility": 3},
    "B": {"growth": 3, "stability": 5, "cost": 2, "reversibility": 4}
  }
}
```

`context` 可为空。三个偏好值以及每条路径的四项自评分数均需为 1–5 的整数。输入不合法时返回 HTTP 400 和错误说明。

可选 `market_scope` 示例：

```json
{
  "enabled": true,
  "paths": {
    "A": {"country_code": "CHN", "industry_code": "manufacturing", "start_year": 2020, "end_year": 2025},
    "B": {"country_code": "USA", "industry_code": "manufacturing", "start_year": 2020, "end_year": 2025}
  }
}
```

将该对象放在分析请求根级的 `market_scope` 字段中。省略或关闭查询时不访问外部数据。启用后只有 A、B 两侧国家、行业和年度范围都通过校验才会查询；市场结果位于独立的 `market_evidence` 对象中，不参与得分。

## 测试

```bash
python -m unittest discover -s tests -v
```

## 项目结构

```text
cyber-life-analyzer/
├── app.py                 # Flask 应用与 API 路由
├── analyzer.py            # 评分、权重、行动建议与输入校验
├── market_data.py         # 可选 WDI 查询、来源元数据、缓存与可比性检查
├── requirements.txt       # Flask 依赖
├── templates/
│   └── index.html         # 表单与结果结构
├── static/
│   ├── app.js             # 表单交互与结果渲染
│   └── style.css          # 视觉样式与响应式布局
└── tests/                 # 评分、输入校验、市场数据与 API mock 测试
```
