const form = document.querySelector('#analysis-form');
const errorBox = document.querySelector('#form-error');
const resultContent = document.querySelector('#result-content');
const emptyState = document.querySelector('#empty-state');
const canvas = document.querySelector('#energy-chart');
let latestResult = null;

form.querySelectorAll('input[type="range"]').forEach((slider) => {
  slider.addEventListener('input', () => {
    form.querySelector(`[data-value="${slider.name}"]`).textContent = slider.value;
  });
});

const contextInput = form.elements.context;
const charCount = document.querySelector('.char-count');
const updateCount = () => { charCount.textContent = `${contextInput.value.length} / 300`; };
contextInput.addEventListener('input', updateCount);
updateCount();

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  errorBox.textContent = '';
  const button = form.querySelector('.analyze-button');
  button.disabled = true;
  button.classList.add('loading');
  button.querySelector('span:first-child').textContent = '正在推演…';
  document.querySelector('.live-tag').innerHTML = '<i></i> 正在计算';
  const payload = Object.fromEntries(new FormData(form).entries());
  for (const key of ['risk_tolerance', 'resources', 'urgency']) payload[key] = Number(payload[key]);
  try {
    const response = await fetch('/api/analyze', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || '分析暂时无法完成，请稍后重试。');
    latestResult = data;
    renderResult(data);
  } catch (error) {
    errorBox.textContent = error.message || '网络连接异常，请确认 Flask 服务正在运行。';
    document.querySelector('.live-tag').innerHTML = '<i class="error-dot"></i> 输入待修正';
  } finally {
    button.disabled = false;
    button.classList.remove('loading');
    button.querySelector('span:first-child').textContent = '生成趋势推演';
  }
});

function renderResult(data) {
  emptyState.classList.add('hidden');
  resultContent.classList.remove('hidden');
  document.querySelector('.live-tag').innerHTML = '<i></i> 推演已完成';
  document.querySelector('.result-time').textContent = new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit' }).format(new Date());
  document.querySelector('#confidence').textContent = data.trend_analysis.confidence;
  document.querySelector('#trend-summary').textContent = data.trend_analysis.summary;
  document.querySelector('#drivers').replaceChildren(...data.trend_analysis.drivers.map((driver, index) => {
    const item = document.createElement('span'); item.innerHTML = `<i>0${index + 1}</i>`; item.append(document.createTextNode(driver)); return item;
  }));
  document.querySelector('#path-keys').replaceChildren(...data.paths.map((path) => {
    const item = document.createElement('div'); item.className = `path-key path-${path.id.toLowerCase()}`;
    item.innerHTML = `<span>${path.id}</span><div><b>${escapeHtml(path.label)}</b><small>趋势匹配度 ${path.fit_score}</small></div>`;
    return item;
  }));
  document.querySelector('#phases').replaceChildren(...data.phases.map((phase) => {
    const item = document.createElement('article'); item.className = `phase phase-${phase.tone}`;
    item.innerHTML = `<span class="phase-year">${escapeHtml(phase.year)}</span><div><h4>${escapeHtml(phase.title)}</h4><p>${escapeHtml(phase.description)}</p></div>`; return item;
  }));
  document.querySelector('#nodes').replaceChildren(...data.decision_points.map((node) => {
    const item = document.createElement('article'); item.className = `node node-${node.kind}`;
    item.innerHTML = `<span class="node-window">${escapeHtml(node.window)}</span><div><h4>${escapeHtml(node.title)}</h4><p>${escapeHtml(node.detail)}</p></div><span class="node-type">${node.kind === 'risk' ? '风险' : '机遇'}</span>`; return item;
  }));
  const rec = data.recommendation;
  document.querySelector('#preferred-badge').textContent = `优先探索 · 路径 ${rec.preferred_path}`;
  document.querySelector('#recommendation-title').textContent = rec.preferred_label;
  document.querySelector('#recommendation-summary').textContent = rec.summary;
  document.querySelector('#next-step').textContent = rec.next_step;
  document.querySelector('#caveat').textContent = data.trend_analysis.caveat;
  requestAnimationFrame(() => drawChart(data.paths));
}

function drawChart(paths) {
  const rect = canvas.getBoundingClientRect();
  const scale = window.devicePixelRatio || 1;
  canvas.width = rect.width * scale; canvas.height = 190 * scale;
  const ctx = canvas.getContext('2d'); ctx.scale(scale, scale);
  const width = rect.width; const height = 190; const left = 12; const right = width - 14; const top = 12; const bottom = height - 12;
  ctx.strokeStyle = 'rgba(171, 207, 194, .11)'; ctx.lineWidth = 1;
  [0, 1, 2, 3].forEach((i) => { const y = top + (bottom - top) * i / 3; ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(right, y); ctx.stroke(); });
  const colors = { A: '#71f2c0', B: '#9ba4ff' };
  paths.forEach((path) => {
    const values = [50, ...path.energy.map((point) => point.value)];
    const pts = values.map((value, index) => ({ x: left + (right - left) * index / 3, y: bottom - (value - 20) / 65 * (bottom - top) }));
    ctx.beginPath(); ctx.moveTo(pts[0].x, pts[0].y);
    pts.slice(1).forEach((point) => ctx.lineTo(point.x, point.y));
    ctx.strokeStyle = colors[path.id]; ctx.lineWidth = 2.5; ctx.lineJoin = 'round'; ctx.stroke();
    pts.forEach((point) => { ctx.beginPath(); ctx.arc(point.x, point.y, 3.5, 0, Math.PI * 2); ctx.fillStyle = colors[path.id]; ctx.fill(); });
  });
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
}

document.querySelector('#reset-button').addEventListener('click', () => {
  resultContent.classList.add('hidden'); emptyState.classList.remove('hidden'); latestResult = null;
  document.querySelector('.live-tag').innerHTML = '<i></i> 等待输入';
  form.scrollIntoView({ behavior: 'smooth', block: 'start' });
});
window.addEventListener('resize', () => { if (latestResult) drawChart(latestResult.paths); });
