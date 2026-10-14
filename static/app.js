const form = document.querySelector('#analysis-form');
const errorBox = document.querySelector('#form-error');
const resultContent = document.querySelector('#result-content');
const emptyState = document.querySelector('#empty-state');
const resultStatus = document.querySelector('#result-status');
const engineStatus = document.querySelector('#engine-status');
const resultsPanel = document.querySelector('#results');
const factorKeys = ['growth', 'stability', 'cost', 'reversibility'];
const pathNameFields = [
  [form.elements.option_a, '路径 A'],
  [form.elements.option_b, '路径 B'],
];

function validatePathNames() {
  pathNameFields.forEach(([field, label]) => {
    const hasNonWhitespace = field.value.replace(/\s+/gu, '').length > 0;
    field.setCustomValidity(hasNonWhitespace ? '' : `${label} 不能为空。`);
  });
}

pathNameFields.forEach(([field]) => field.addEventListener('input', validatePathNames));
validatePathNames();

form.querySelectorAll('input[type="range"]').forEach((slider) => {
  const output = slider.closest('label').querySelector('output');
  const updateValue = () => { output.textContent = slider.value; };
  slider.addEventListener('input', updateValue);
  updateValue();
});

const contextInput = form.elements.context;
const charCount = document.querySelector('.char-count');
const updateCount = () => { charCount.textContent = `${contextInput.value.length} / 300`; };
contextInput.addEventListener('input', updateCount);
updateCount();

const marketEnabled = document.querySelector('#market-enabled');
const marketControls = document.querySelector('#market-controls');
marketEnabled.addEventListener('change', () => {
  marketControls.hidden = !marketEnabled.checked;
});

const currentYear = new Date().getFullYear();
form.querySelectorAll('input[name$="_start_year"], input[name$="_end_year"]').forEach((input) => {
  input.max = String(currentYear);
});
form.elements.market_a_end_year.value = String(currentYear - 1);
form.elements.market_b_end_year.value = String(currentYear - 1);
form.elements.market_a_start_year.value = String(currentYear - 6);
form.elements.market_b_start_year.value = String(currentYear - 6);

document.querySelector('#copy-market-scope').addEventListener('click', () => {
  ['country', 'city', 'industry', 'occupation', 'seniority', 'start_year', 'end_year'].forEach((field) => {
    form.elements['market_b_' + field].value = form.elements['market_a_' + field].value;
  });
  form.elements.market_b_country.focus();
});

document.querySelector('#load-example-button').addEventListener('click', () => {
  form.elements.option_a.value = '换一份更有成长空间的工作';
  form.elements.option_b.value = '留在当前岗位继续积累';
  form.elements.context.value = '工作稳定，但成长速度变慢；希望兼顾收入和长期发展。';
  validatePathNames();

  const exampleRatings = {
    rating_a_growth: 5,
    rating_a_stability: 2,
    rating_a_cost: 4,
    rating_a_reversibility: 3,
    rating_b_growth: 3,
    rating_b_stability: 5,
    rating_b_cost: 2,
    rating_b_reversibility: 4,
  };
  Object.entries(exampleRatings).forEach(([name, value]) => {
    form.elements[name].value = value;
    form.elements[name].dispatchEvent(new Event('input', { bubbles: true }));
  });
  updateCount();
  form.elements.option_a.focus();
});

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  errorBox.textContent = '';
  const button = form.querySelector('.analyze-button');
  const buttonLabel = button.querySelector('span:first-child');
  resultContent.classList.add('hidden');
  emptyState.classList.remove('hidden');
  button.disabled = true;
  button.classList.add('loading');
  buttonLabel.textContent = marketEnabled.checked ? '正在比较并查询公开数据…' : '正在比较…';
  engineStatus.textContent = '正在计算';
  resultStatus.textContent = marketEnabled.checked ? '正在比较路径并查询公开统计。' : '正在比较两条路径。';

  const formData = new FormData(form);
  const payload = {
    option_a: formData.get('option_a'),
    option_b: formData.get('option_b'),
    context: formData.get('context'),
    risk_tolerance: Number(formData.get('risk_tolerance')),
    resources: Number(formData.get('resources')),
    urgency: Number(formData.get('urgency')),
    path_ratings: {
      A: Object.fromEntries(factorKeys.map((key) => [key, Number(formData.get(`rating_a_${key}`))])),
      B: Object.fromEntries(factorKeys.map((key) => [key, Number(formData.get(`rating_b_${key}`))])),
    },
  };

  payload.market_scope = {
    enabled: marketEnabled.checked,
    paths: {
      A: collectMarketScope('a', formData),
      B: collectMarketScope('b', formData),
    },
  };

  try {
    const response = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || '比较暂时无法完成，请检查输入后重试。');
    renderResult(data);
  } catch (error) {
    const message = error.message || '网络连接异常，请确认本地服务正在运行。';
    errorBox.textContent = message;
    engineStatus.textContent = '输入待修正';
    resultStatus.textContent = message;
  } finally {
    button.disabled = false;
    button.classList.remove('loading');
    buttonLabel.textContent = '比较这两条路径';
  }
});

function makeTextElement(tagName, className, text) {
  const element = document.createElement(tagName);
  if (className) element.className = className;
  element.textContent = text;
  return element;
}

function collectMarketScope(pathId, formData) {
  return {
    country_code: formData.get('market_' + pathId + '_country'),
    province_city: formData.get('market_' + pathId + '_city'),
    industry_code: formData.get('market_' + pathId + '_industry'),
    occupation_code: formData.get('market_' + pathId + '_occupation'),
    seniority: formData.get('market_' + pathId + '_seniority'),
    start_year: formData.get('market_' + pathId + '_start_year'),
    end_year: formData.get('market_' + pathId + '_end_year'),
  };
}

function renderScoreCard(path) {
  const card = document.createElement('article');
  card.className = `score-card score-${path.id.toLowerCase()}`;

  const heading = document.createElement('div');
  heading.className = 'score-card-heading';
  heading.append(makeTextElement('span', 'path-mark', path.id));
  const labelGroup = document.createElement('div');
  labelGroup.className = 'score-card-label';
  labelGroup.append(makeTextElement('h4', '', path.label));
  labelGroup.append(makeTextElement('small', '', `当前条件匹配分 · ${path.fit_score} / 100`));
  heading.append(labelGroup);
  card.append(heading);

  const meter = document.createElement('div');
  meter.className = 'score-meter';
  meter.setAttribute('role', 'progressbar');
  meter.setAttribute('aria-label', `${path.label}当前条件匹配分`);
  meter.setAttribute('aria-valuemin', '0');
  meter.setAttribute('aria-valuemax', '100');
  meter.setAttribute('aria-valuenow', String(path.fit_score));
  const meterFill = document.createElement('span');
  meterFill.style.width = `${Math.max(0, Math.min(100, path.fit_score))}%`;
  meter.append(meterFill);
  card.append(meter);

  const tableWrap = document.createElement('div');
  tableWrap.className = 'score-table-wrap';
  const table = document.createElement('table');
  table.className = 'score-table';
  const thead = document.createElement('thead');
  const headerRow = document.createElement('tr');
  ['维度', '自评', '权重', '贡献'].forEach((label) => {
    const header = makeTextElement('th', '', label);
    header.scope = 'col';
    headerRow.append(header);
  });
  thead.append(headerRow);
  table.append(thead);

  const tbody = document.createElement('tbody');
  path.breakdown.forEach((item) => {
    const row = document.createElement('tr');
    const factorHeader = makeTextElement('th', '', item.label);
    factorHeader.scope = 'row';
    row.append(factorHeader);
    row.append(makeTextElement('td', '', `${item.rating} / 5`));
    row.append(makeTextElement('td', '', `${item.weight}%`));
    row.append(makeTextElement('td', '', `${item.contribution.toFixed(1)} 分`));
    tbody.append(row);
  });
  table.append(tbody);
  tableWrap.append(table);
  card.append(tableWrap);
  return card;
}

function renderResult(data) {
  emptyState.classList.add('hidden');
  resultContent.classList.remove('hidden');
  engineStatus.textContent = '比较完成';

  const { comparison, recommendation } = data;
  const isBalanced = comparison.status === 'balanced';
  document.querySelector('#comparison-summary').textContent = comparison.summary;
  document.querySelector('#comparison-badge').textContent = isBalanced
    ? `差距 ${comparison.score_gap.toFixed(1)} / 100 · 暂不排序`
    : `路径 ${recommendation.preferred_path} 暂时领先 ${comparison.score_gap.toFixed(1)} 分`;
  document.querySelector('#comparison-note').textContent =
    `重点核对：${comparison.focus_dimension.label}。背景备注只供你回看，不参与评分。`;

  renderSensitivity(data.sensitivity);
  renderMarketEvidence(data.market_evidence);
  document.querySelector('#score-cards').replaceChildren(...data.paths.map(renderScoreCard));
  const weightList = document.querySelector('#weight-list');
  const baseWeights = data.scoring.base_weights;
  document.querySelector('#base-weights').textContent =
    `基准权重：成长空间 ${baseWeights.growth}%、稳定性 ${baseWeights.stability}%、成本负担 ${baseWeights.cost}%、可逆性 ${baseWeights.reversibility}%。`;
  weightList.replaceChildren(...factorKeys.map((key) => {
    const factor = data.paths[0].breakdown.find((item) => item.key === key);
    return makeTextElement('li', '', `${factor.label} ${data.scoring.weights[key]}%`);
  }));
  document.querySelector('#weight-rules').replaceChildren(...data.scoring.weight_rules.map((rule) => {
    return makeTextElement('li', '', rule);
  }));
  document.querySelector('#checkpoints').replaceChildren(...data.checkpoints.map((checkpoint) => {
    const item = document.createElement('article');
    item.className = 'checkpoint';
    item.append(makeTextElement('span', 'checkpoint-window', checkpoint.window));
    const content = document.createElement('div');
    content.append(makeTextElement('h4', '', checkpoint.title));
    content.append(makeTextElement('p', '', checkpoint.question));
    item.append(content);
    return item;
  }));

  document.querySelector('#preferred-badge').textContent = isBalanced
    ? '保留两种可能'
    : `路径 ${recommendation.preferred_path} 暂时较适配`;
  document.querySelector('#recommendation-title').textContent = recommendation.title;
  document.querySelector('#recommendation-summary').textContent = recommendation.summary;
  document.querySelector('#experiment').textContent = recommendation.experiment;
  document.querySelector('#metric').textContent = recommendation.metric;
  document.querySelector('#continue-if').textContent = recommendation.continue_if;
  document.querySelector('#pause-if').textContent = recommendation.pause_if;
  document.querySelector('#caveat').textContent = data.caveat;
  resultStatus.textContent = `比较完成。${comparison.summary}`;

  const evidenceStatus = marketStatusLabels[data.market_evidence?.status] || '未查询';
  resultStatus.textContent = resultStatus.textContent + ' 市场证据状态：' + evidenceStatus + '。';

  if (window.matchMedia('(max-width: 760px)').matches) {
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    requestAnimationFrame(() => resultsPanel.scrollIntoView({
      behavior: reducedMotion ? 'auto' : 'smooth',
      block: 'start',
    }));
  }
}

function leaderName(leader) {
  return leader ? '路径 ' + leader + ' 领先' : '当前条件下两条路径接近';
}

function renderSensitivity(sensitivity) {
  const summary = document.querySelector('#sensitivity-summary');
  const badge = document.querySelector('#sensitivity-badge');
  const list = document.querySelector('#sensitivity-details');
  if (!sensitivity) {
    summary.textContent = '本次未返回敏感性检查。';
    badge.textContent = '暂不可用';
    list.replaceChildren();
    return;
  }
  summary.textContent = sensitivity.summary;
  badge.textContent = sensitivity.status === 'sensitive'
    ? '结果对偏好设置敏感'
    : '±1 档内领先关系未改变';
  list.replaceChildren(...sensitivity.checks.map((check) => {
    const item = document.createElement('li');
    const range = check.lower_value + ' 档：' + leaderName(check.lower_leader)
      + '；' + check.upper_value + ' 档：' + leaderName(check.upper_leader);
    item.append(makeTextElement('strong', '', check.label));
    item.append(makeTextElement('span', '', '当前 ' + check.current + ' 档 · ' + range));
    if (check.changes_leader) item.classList.add('sensitive');
    return item;
  }));
}

const marketStatusLabels = {
  available: '数据可用',
  partial: '部分数据可用',
  stale: '数据年份较旧',
  rate_limited: '数据源限流',
  no_data: '所选范围暂无数据',
  unavailable: '数据源暂不可用',
  incomplete_scope: '查询范围未填完整',
  disabled: '未启用查询',
};

function createSourceLink(label, url) {
  const link = makeTextElement('a', '', label);
  link.href = url;
  link.target = '_blank';
  link.rel = 'noopener noreferrer';
  return link;
}

function renderMarketMetric(metric) {
  const item = document.createElement('article');
  item.className = 'market-metric';
  item.append(makeTextElement('h5', '', metric.name));
  const value = Number(metric.value).toLocaleString(undefined, { maximumFractionDigits: 1 });
  item.append(makeTextElement('strong', '', value + ' ' + metric.unit));
  const freshness = metric.freshness_status === 'stale' ? ' · 数据年份较旧' : '';
  item.append(makeTextElement('p', '', metric.change_basis + ' · 观测年份 ' + metric.observation_year + freshness));
  return item;
}

function renderMarketPath(path) {
  const card = document.createElement('article');
  card.className = 'market-path-card market-path-' + String(path.id).toLowerCase();
  const title = [path.country, path.industry].filter(Boolean).join(' · ') || '未完成范围选择';
  card.append(makeTextElement('h4', '', '路径 ' + path.id + ' · ' + title));
  card.append(makeTextElement('p', 'market-path-status', marketStatusLabels[path.status] || path.status));
  if (path.country_code && path.period_start && path.period_end) {
    card.append(makeTextElement('p', 'market-local-scope', '查询范围：' + path.country + ' · '
      + path.industry + ' · ' + path.period_start + '–' + path.period_end + ' 年'));
  }

  if (path.province_city || path.occupation_code || path.seniority) {
    const localScope = [
      path.province_city ? '填写的地区：' + path.province_city : '',
      path.occupation_code ? '填写的职业代码：' + path.occupation_code : '',
      path.seniority ? '资历：' + path.seniority : '',
    ].filter(Boolean).join(' · ');
    card.append(makeTextElement('p', 'market-local-scope', localScope + '。这些维度不在当前数据源口径内。'));
  }

  if (path.metrics && path.metrics.length) {
    const metrics = document.createElement('div');
    metrics.className = 'market-metrics';
    path.metrics.forEach((metric) => metrics.append(renderMarketMetric(metric)));
    card.append(metrics);
  } else {
    card.append(makeTextElement('p', 'market-no-data', '没有可显示的实际数值；不会使用默认值或推测补齐。'));
  }

  if (path.metrics && path.metrics.length) {
    const details = document.createElement('details');
    details.className = 'market-source-details';
    details.append(makeTextElement('summary', '', '统计口径、更新时间与来源'));
    const body = document.createElement('div');
    body.className = 'market-source-body';
    const scope = path.country + '（' + path.country_code + '） · ' + path.industry
      + '（WDI 行业汇总口径） · ' + path.period_start + '–' + path.period_end;
    body.append(makeTextElement('p', '', '统计范围：' + scope));
    body.append(makeTextElement('p', '', '更新频率：' + path.update_frequency));
    body.append(makeTextElement('p', '', '最新观测：' + (path.latest_observation_year ?? '无') + ' · ' + path.freshness_label));
    body.append(makeTextElement('p', '', '本次抓取：' + (path.retrieved_at || '不可用')));
    body.append(makeTextElement('p', '', path.publication_note));
    body.append(makeTextElement('p', '', path.limitation));
    path.metrics.forEach((metric) => {
      const values = metric.series.map((point) => point.year + ': ' + point.value + ' ' + metric.unit).join('；');
      body.append(makeTextElement('p', '', '指标代码 ' + metric.indicator_code + ' · ' + metric.change_basis));
      body.append(makeTextElement('p', '', '所选范围内年度观测：' + values));
      body.append(createSourceLink('原始指标 ' + metric.indicator_code, metric.source_url));
      body.append(document.createTextNode(' · '));
      body.append(createSourceLink('API 数据 ' + metric.indicator_code, metric.api_url));
      body.append(document.createElement('br'));
    });
    body.append(createSourceLink('许可：' + path.license, path.license_url));
    details.append(body);
    card.append(details);
  }
  return card;
}

function renderMarketEvidence(evidence) {
  const summary = document.querySelector('#market-evidence-summary');
  const cards = document.querySelector('#market-evidence-paths');
  const comparisons = document.querySelector('#market-comparability');
  if (!evidence) {
    summary.textContent = '未返回市场证据状态。';
    cards.replaceChildren();
    comparisons.replaceChildren();
    return;
  }
  const status = marketStatusLabels[evidence.status] || evidence.status;
  summary.textContent = status + '。' + (evidence.message || '');
  cards.replaceChildren(...(evidence.paths || []).map(renderMarketPath));
  comparisons.replaceChildren(...(evidence.comparability || []).map((item) => {
    const row = document.createElement('article');
    row.className = 'market-comparison-row ' + (item.comparable ? 'is-comparable' : 'not-comparable');
    const comparisonLabel = item.comparison_level === 'cross_country_macro'
      ? '仅跨国宏观对照'
      : (item.comparable ? '口径可比' : '不可直接比较');
    row.append(makeTextElement('strong', '', item.label + '：' + comparisonLabel));
    row.append(makeTextElement('p', '', item.reason));
    return row;
  }));
}

document.querySelector('#reset-button').addEventListener('click', () => {
  resultContent.classList.add('hidden');
  emptyState.classList.remove('hidden');
  engineStatus.textContent = '等待输入';
  resultStatus.textContent = '已返回输入区域。';
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  form.scrollIntoView({ behavior: reducedMotion ? 'auto' : 'smooth', block: 'start' });
  form.elements.option_a.focus({ preventScroll: true });
});
