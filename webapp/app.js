/* ============================================================
   HCERES ACENTAURI Dashboard — Application Logic
   ============================================================ */

const DATA_DIR = 'data/';

const CHART_COLORS = {
  indigo: '#6366f1', violet: '#8b5cf6', cyan: '#06b6d4',
  emerald: '#10b981', amber: '#f59e0b', pink: '#ec4899',
  red: '#ef4444', blue: '#3b82f6', teal: '#14b8a6', orange: '#f97316',
};
const PALETTE = Object.values(CHART_COLORS);

const COUNTRY_NAMES = {
  us:'États-Unis',fr:'France',cn:'Chine',ro:'Roumanie',kr:'Corée du Sud',
  ae:'Émirats Arabes Unis',at:'Autriche',it:'Italie',sg:'Singapour',
  pt:'Portugal',jp:'Japon',au:'Australie',de:'Allemagne',se:'Suède',
  pl:'Pologne',es:'Espagne',ar:'Argentine',is:'Islande',gb:'Royaume-Uni',
  br:'Brésil',in:'Inde',ca:'Canada',ch:'Suisse',nl:'Pays-Bas',be:'Belgique',
};

function countryFlag(code) {
  if (!code || code.length < 2) return '🌍';
  const c = code.toUpperCase();
  return String.fromCodePoint(...[...c].map(ch => 0x1F1E6 + ch.charCodeAt(0) - 65));
}

// --- CSV Loading ---
async function loadCSV(filename) {
  try {
    const resp = await fetch(DATA_DIR + filename);
    if (!resp.ok) throw new Error(resp.status);
    const text = await resp.text();
    return Papa.parse(text.trim(), { header: true, skipEmptyLines: true, dynamicTyping: true }).data;
  } catch (e) {
    console.warn(`Could not load ${filename}:`, e);
    return [];
  }
}

function getMetric(data, name, fallback = '—') {
  const row = data.find(r => r.indicator === name);
  if (!row) return fallback;
  const v = row.value;
  if (v == null || v === '') return fallback;
  if (typeof v === 'number') {
    if (v >= 0 && v <= 1 && name.includes('rate') || name.includes('share'))
      return (v * 100).toFixed(1) + '%';
    return Number.isInteger(v) ? String(v) : v.toFixed(1);
  }
  return String(v);
}

// --- Chart.js Defaults ---
function setupChartDefaults() {
  Chart.defaults.color = '#94a3b8';
  Chart.defaults.borderColor = 'rgba(255,255,255,0.06)';
  Chart.defaults.font.family = "'Inter', sans-serif";
  Chart.defaults.font.size = 12;
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.pointStyleWidth = 10;
  Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(15,20,40,0.95)';
  Chart.defaults.plugins.tooltip.borderColor = 'rgba(99,102,241,0.3)';
  Chart.defaults.plugins.tooltip.borderWidth = 1;
  Chart.defaults.plugins.tooltip.cornerRadius = 8;
  Chart.defaults.plugins.tooltip.padding = 10;
  Chart.defaults.plugins.tooltip.titleFont = { weight: '600' };
  Chart.defaults.animation.duration = 1200;
  Chart.defaults.animation.easing = 'easeOutQuart';
}

// --- Chart Builders ---
function createBarChart(canvasId, labels, datasets, opts = {}) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;
  return new Chart(ctx, {
    type: 'bar',
    data: { labels, datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: datasets.length > 1 } },
      scales: {
        x: { grid: { display: false }, ticks: { maxRotation: opts.rotateX ? 45 : 0 } },
        y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.04)' } }
      },
      ...opts.extra
    }
  });
}

function createHorizontalBar(canvasId, labels, values, colors) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;
  return new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: colors || labels.map((_, i) => PALETTE[i % PALETTE.length] + '99'),
        borderColor: colors || labels.map((_, i) => PALETTE[i % PALETTE.length]),
        borderWidth: 1, borderRadius: 4, barThickness: 20,
      }]
    },
    options: {
      indexAxis: 'y', responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.04)' } },
        y: { grid: { display: false }, ticks: { font: { size: 11 } } }
      }
    }
  });
}

function createDoughnut(canvasId, labels, values, colors) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;
  return new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: colors || labels.map((_, i) => PALETTE[i % PALETTE.length] + 'cc'),
        borderColor: 'rgba(10,14,26,0.8)', borderWidth: 2,
        hoverOffset: 8,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false, cutout: '65%',
      plugins: {
        legend: { position: 'bottom', labels: { padding: 16, font: { size: 11 } } }
      }
    }
  });
}

function createLineChart(canvasId, labels, datasets) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;
  return new Chart(ctx, {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: datasets.length > 1 } },
      scales: {
        x: { grid: { display: false } },
        y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.04)' } }
      },
      elements: { point: { radius: 5, hoverRadius: 7 }, line: { tension: 0.3 } }
    }
  });
}

// --- Animated Counter ---
function animateCounters() {
  document.querySelectorAll('[data-counter]').forEach(el => {
    const target = parseFloat(el.dataset.counter);
    const suffix = el.dataset.suffix || '';
    const isFloat = !Number.isInteger(target);
    let start = 0;
    const duration = 1400;
    const startTime = performance.now();
    function step(now) {
      const progress = Math.min((now - startTime) / duration, 1);
      const ease = 1 - Math.pow(1 - progress, 3);
      const current = start + (target - start) * ease;
      el.textContent = (isFloat ? current.toFixed(1) : Math.round(current)) + suffix;
      if (progress < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  });
}

// --- Scroll Animation ---
function setupScrollObserver() {
  const obs = new IntersectionObserver((entries) => {
    entries.forEach(e => { if (e.isIntersecting) { e.target.classList.add('visible'); } });
  }, { threshold: 0.1 });
  document.querySelectorAll('.fade-in-section').forEach(el => obs.observe(el));
}

// --- Sidebar Active Link ---
function setupNavHighlight() {
  const sections = document.querySelectorAll('.dashboard-section[id]');
  const links = document.querySelectorAll('.nav-link');
  const obs = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        links.forEach(l => l.classList.remove('active'));
        const link = document.querySelector(`.nav-link[href="#${e.target.id}"]`);
        if (link) link.classList.add('active');
      }
    });
  }, { rootMargin: '-20% 0px -70% 0px' });
  sections.forEach(s => obs.observe(s));
}

// --- Mobile Sidebar ---
function setupMobileToggle() {
  const btn = document.getElementById('mobile-toggle');
  const sidebar = document.querySelector('.sidebar');
  if (!btn || !sidebar) return;
  btn.addEventListener('click', () => sidebar.classList.toggle('open'));
  document.querySelectorAll('.nav-link').forEach(l => {
    l.addEventListener('click', () => sidebar.classList.remove('open'));
  });
}

// --- Gauge Animations ---
function animateGauges() {
  document.querySelectorAll('.gauge-bar-fill').forEach(el => {
    const target = el.dataset.width;
    if (target) setTimeout(() => { el.style.width = target; }, 300);
  });
}

// --- Build a simple HTML table ---
function buildTable(containerId, headers, rows) {
  const wrapper = document.getElementById(containerId);
  if (!wrapper || !rows.length) return;
  let html = '<table class="data-table"><thead><tr>';
  headers.forEach(h => { html += `<th>${h.label}</th>`; });
  html += '</tr></thead><tbody>';
  rows.forEach(row => {
    html += '<tr>';
    headers.forEach(h => {
      let val = row[h.key] ?? '—';
      if (h.render) val = h.render(val, row);
      html += `<td>${val}</td>`;
    });
    html += '</tr>';
  });
  html += '</tbody></table>';
  wrapper.innerHTML = html;
}

// ============================================================
// MAIN INITIALIZATION
// ============================================================
document.addEventListener('DOMContentLoaded', async () => {
  setupChartDefaults();
  setupScrollObserver();
  setupNavHighlight();
  setupMobileToggle();

  // Load all data in parallel
  const [summary, annual, annualDoc, docType, authors, venues, partners, countries, collabSummary, openScience, annualFull] = await Promise.all([
    loadCSV('hceres_summary_indicators.csv'),
    loadCSV('annual_statistics.csv'),
    loadCSV('annual_document_type_statistics.csv'),
    loadCSV('document_type_statistics.csv'),
    loadCSV('author_statistics.csv'),
    loadCSV('venue_statistics.csv'),
    loadCSV('partner_laboratory_or_institution_ranking.csv'),
    loadCSV('partner_country_ranking.csv'),
    loadCSV('collaboration_summary.csv'),
    loadCSV('open_science_statistics.csv'),
    loadCSV('annual_full_text_statistics.csv'),
  ]);

  // ---- Hero KPIs ----
  const setHero = (id, val) => {
    const el = document.getElementById(id);
    if (el) { el.dataset.counter = val; el.textContent = '0'; }
  };
  setHero('kpi-publications', getMetric(summary, 'unique_publications', '0'));
  setHero('kpi-members', getMetric(summary, 'identified_or_inferred_members', '0'));

  const fullTextRow = openScience.find(r => r.indicator === 'publications_with_full_text_in_hal');
  const ftPct = fullTextRow && fullTextRow.share != null ? (fullTextRow.share * 100).toFixed(1) : '—';
  const ftEl = document.getElementById('kpi-openaccess');
  if (ftEl) { ftEl.dataset.counter = parseFloat(ftPct) || 0; ftEl.dataset.suffix = '%'; ftEl.textContent = '0'; }

  const countriesCount = countries.length;
  setHero('kpi-countries', String(countriesCount));

  animateCounters();

  // ---- Section: Publications Timeline ----
  if (annual.length) {
    const years = annual.map(r => String(r.year));
    const counts = annual.map(r => r.publication_count);
    createBarChart('chart-pub-year', years, [{
      label: 'Publications', data: counts,
      backgroundColor: CHART_COLORS.indigo + 'bb',
      borderColor: CHART_COLORS.indigo, borderWidth: 1, borderRadius: 6,
    }]);
  }

  if (annualDoc.length) {
    const years = [...new Set(annualDoc.map(r => String(r.year)))].sort();
    const types = [...new Set(annualDoc.map(r => r.doc_type))];
    const datasets = types.map((t, i) => ({
      label: t,
      data: years.map(y => {
        const row = annualDoc.find(r => String(r.year) === y && r.doc_type === t);
        return row ? row.publication_count : 0;
      }),
      backgroundColor: PALETTE[i % PALETTE.length] + 'bb',
      borderColor: PALETTE[i % PALETTE.length],
      borderWidth: 1, borderRadius: 4,
    }));
    createBarChart('chart-pub-type-year', years, datasets, {
      extra: { scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, beginAtZero: true, grid: { color: 'rgba(255,255,255,0.04)' } } } }
    });
  }

  if (docType.length) {
    createDoughnut('chart-doc-donut',
      docType.map(r => r.doc_type),
      docType.map(r => r.publication_count),
      docType.map((_, i) => PALETTE[i % PALETTE.length] + 'cc')
    );
  }

  // ---- Section: Authors ----
  if (authors.length) {
    const top = authors.slice(0, 15);
    createHorizontalBar('chart-authors',
      top.map(r => r.author_name),
      top.map(r => r.publication_count)
    );
    buildTable('table-authors',
      [
        { key: 'author_name', label: 'Auteur' },
        { key: 'publication_count', label: 'Publications' },
        { key: 'first_author_count', label: '1er auteur' },
      ],
      authors.slice(0, 30)
    );
  }

  // ---- Section: Venues ----
  if (venues.length) {
    const topV = venues.slice(0, 12);
    createHorizontalBar('chart-venues',
      topV.map(r => (r.venue || '').substring(0, 55) + ((r.venue || '').length > 55 ? '…' : '')),
      topV.map(r => r.publication_count),
      topV.map(r => r.venue_type === 'journal' ? CHART_COLORS.indigo + '99' : CHART_COLORS.cyan + '99')
    );
    buildTable('table-venues',
      [
        { key: 'venue', label: 'Venue', render: v => `<span style="max-width:300px;display:inline-block;overflow:hidden;text-overflow:ellipsis" title="${v}">${v}</span>` },
        { key: 'venue_type', label: 'Type', render: v => `<span class="pill ${v === 'journal' ? 'badge-journal' : 'badge-conference'}">${v}</span>` },
        { key: 'publication_count', label: 'Pubs' },
      ],
      venues.slice(0, 20)
    );
  }

  // ---- Section: Collaborations ----
  if (partners.length) {
    const topP = partners.slice(0, 12);
    createHorizontalBar('chart-partners',
      topP.map(r => (r.partner || '').substring(0, 50) + ((r.partner || '').length > 50 ? '…' : '')),
      topP.map(r => r.publication_count),
      topP.map(r => {
        if (r.partner_type_inferred === 'academic_or_public_research') return CHART_COLORS.emerald + '99';
        if (r.partner_type_inferred === 'industrial_or_private') return CHART_COLORS.amber + '99';
        return CHART_COLORS.blue + '66';
      })
    );
  }

  // Country list
  const countryList = document.getElementById('country-list');
  if (countryList && countries.length) {
    countryList.innerHTML = countries.slice(0, 15).map(r => {
      const name = COUNTRY_NAMES[r.country] || r.country.toUpperCase();
      return `<div class="country-item">
        <span class="country-flag">${countryFlag(r.country)}</span>
        <div class="country-info">
          <div class="country-name">${name}</div>
          <div class="country-count">${r.publication_count} publication${r.publication_count > 1 ? 's' : ''}</div>
        </div>
      </div>`;
    }).join('');
  }

  // Collaboration KPIs
  if (collabSummary.length) {
    const setCollab = (id, name) => {
      const el = document.getElementById(id);
      const row = collabSummary.find(r => r.indicator === name);
      if (el && row) el.textContent = typeof row.value === 'number' && row.value <= 1 ? (row.value * 100).toFixed(0) + '%' : Math.round(row.value);
    };
    setCollab('collab-external', 'publications_with_external_partners');
    setCollab('collab-share', 'share_with_external_partners');
    setCollab('collab-distinct', 'distinct_external_partners');
    setCollab('collab-countries', 'distinct_countries');
  }

  // ---- Section: Open Science ----
  if (openScience.length) {
    const ftRow = openScience.find(r => r.indicator === 'publications_with_full_text_in_hal');
    const noFtRow = openScience.find(r => r.indicator === 'publications_without_full_text_in_hal');
    const doiRow = openScience.find(r => r.indicator === 'publications_with_doi');
    const noDoiRow = openScience.find(r => r.indicator === 'publications_without_doi');

    if (ftRow && noFtRow) {
      createDoughnut('chart-fulltext', ['Texte intégral', 'Sans texte'],
        [ftRow.value, noFtRow.value], [CHART_COLORS.emerald + 'cc', 'rgba(100,116,139,0.4)']);
    }
    if (doiRow && noDoiRow) {
      createDoughnut('chart-doi', ['Avec DOI', 'Sans DOI'],
        [doiRow.value, noDoiRow.value], [CHART_COLORS.cyan + 'cc', 'rgba(100,116,139,0.4)']);
    }

    // Gauge bars
    const setGauge = (id, valueId, share) => {
      const bar = document.getElementById(id);
      const valEl = document.getElementById(valueId);
      if (bar && share != null) { bar.dataset.width = (share * 100).toFixed(1) + '%'; }
      if (valEl && share != null) valEl.textContent = (share * 100).toFixed(1) + '%';
    };
    if (ftRow) setGauge('gauge-fulltext', 'val-fulltext', ftRow.share);
    if (doiRow) setGauge('gauge-doi', 'val-doi', doiRow.share);

    const enRow = openScience.find(r => r.indicator === 'english_publications');
    const frRow = openScience.find(r => r.indicator === 'french_publications');
    const totalLang = (enRow?.value || 0) + (frRow?.value || 0);
    if (enRow && totalLang) setGauge('gauge-english', 'val-english', enRow.value / totalLang);
    if (frRow && totalLang) setGauge('gauge-french', 'val-french', frRow.value / totalLang);

    animateGauges();
  }

  if (annualFull.length) {
    createLineChart('chart-fulltext-year',
      annualFull.map(r => String(r.year)),
      [{
        label: 'Taux texte intégral',
        data: annualFull.map(r => r.full_text_share != null ? +(r.full_text_share * 100).toFixed(1) : null),
        borderColor: CHART_COLORS.emerald,
        backgroundColor: CHART_COLORS.emerald + '22',
        fill: true,
      }]
    );
  }

  // Remove loading indicators
  document.querySelectorAll('.loading-spinner').forEach(el => el.remove());
});
