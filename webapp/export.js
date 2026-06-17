/* ============================================================
   HCERES ACENTAURI Dashboard — Prompt Export for Antigravity
   ============================================================ */

const DATA_DIR_EXPORT = 'data/';

// --- Default HCERES Report Structure ---
const DEFAULT_REPORT_STRUCTURE = `## STRUCTURE DU RAPPORT HCERES

Le rapport doit suivre la structure officielle suivante, adaptée à l'évaluation bibliométrique d'une équipe-projet INRIA :

### 1. Présentation générale
- Périmètre de l'équipe évaluée (nom, tutelles, localisation)
- Période d'évaluation et sources de données
- Méthodologie d'extraction et de traitement des données bibliométriques
- Limites et précautions d'interprétation

### 2. Production scientifique
- Volume total de publications sur la période
- Évolution annuelle de la production (tendances, croissance/décroissance)
- Analyse de la dynamique de publication (accélération, ralentissement)
- Comparaison avec les standards du domaine si pertinent

### 3. Répartition par type de document
- Ventilation articles de revues (ART) vs. communications en conférences (COMM) vs. autres
- Équilibre journal / conférence et interprétation dans le contexte disciplinaire
- Évolution de la répartition au fil des années
- Analyse qualitative des choix de publication

### 4. Auteurs et dynamique d'équipe
- Principaux contributeurs et leur volume de publications
- Analyse des premiers auteurs (leadership scientifique)
- Ratio publications / membre de l'équipe
- Répartition de la production au sein de l'équipe (concentration vs. distribution)
- Identification des dynamiques émergentes (nouveaux contributeurs)

### 5. Supports de publication (Venues)
- Principales revues et conférences ciblées
- Répartition des publications par type de venue
- Diversification des supports de publication
- Positionnement dans les venues majeures du domaine

### 6. Collaborations et rayonnement international
- Nombre et part des publications avec partenaires extérieurs
- Principaux laboratoires et institutions partenaires
- Répartition géographique des collaborations (nombre de pays)
- Analyse des collaborations académiques vs. industrielles
- Évaluation du rayonnement international de l'équipe

### 7. Science ouverte
- Taux de disponibilité du texte intégral sur HAL
- Couverture DOI des publications
- Répartition linguistique (français/anglais)
- Évolution des indicateurs de science ouverte sur la période
- Conformité avec la politique nationale de science ouverte

### 8. Synthèse et recommandations
- Points forts identifiés (au format SWOT si pertinent)
- Axes d'amélioration
- Recommandations opérationnelles pour la prochaine période
- Conclusion générale sur la qualité et l'impact de la production scientifique`;

// --- Load CSV helper ---
async function loadCSVExport(filename) {
  try {
    const resp = await fetch(DATA_DIR_EXPORT + filename);
    if (!resp.ok) throw new Error(resp.status);
    const text = await resp.text();
    return Papa.parse(text.trim(), { header: true, skipEmptyLines: true, dynamicTyping: true }).data;
  } catch (e) {
    return [];
  }
}

function csvToText(data, maxRows = 50) {
  if (!data || !data.length) return '(aucune donnée)';
  const cols = Object.keys(data[0]);
  const rows = data.slice(0, maxRows);
  let text = cols.join(' | ') + '\n';
  text += cols.map(() => '---').join(' | ') + '\n';
  rows.forEach(r => { text += cols.map(c => r[c] ?? '').join(' | ') + '\n'; });
  if (data.length > maxRows) text += `... (${data.length - maxRows} lignes supplémentaires)\n`;
  return text;
}

// --- Build the full prompt ---
async function buildFullPrompt(language, customStructure) {
  const [summary, annual, docType, authors, venues, partners, countries, collabSummary, openScience, annualFull] = await Promise.all([
    loadCSVExport('hceres_summary_indicators.csv'),
    loadCSVExport('annual_statistics.csv'),
    loadCSVExport('document_type_statistics.csv'),
    loadCSVExport('author_statistics.csv'),
    loadCSVExport('venue_statistics.csv'),
    loadCSVExport('partner_laboratory_or_institution_ranking.csv'),
    loadCSVExport('partner_country_ranking.csv'),
    loadCSVExport('collaboration_summary.csv'),
    loadCSVExport('open_science_statistics.csv'),
    loadCSVExport('annual_full_text_statistics.csv'),
  ]);

  const lang = language === 'en' ? 'English' : 'French';
  const reportStructure = customStructure || DEFAULT_REPORT_STRUCTURE;

  return `# RAPPORT HCERES — Requête de génération automatique
# Équipe: ACENTAURI · INRIA Sophia Antipolis
# Période: 2022–2026
# Langue: ${lang}
# Date de génération du prompt: ${new Date().toISOString().slice(0, 16).replace('T', ' ')}

═══════════════════════════════════════════════════════════════
INSTRUCTIONS
═══════════════════════════════════════════════════════════════

Tu es un expert en évaluation de la recherche spécialisé dans les évaluations HCERES (Haut Conseil de l'Évaluation de la Recherche et de l'Enseignement Supérieur) pour les équipes de recherche françaises. Rédige en ${lang === 'English' ? 'anglais' : 'français'}.

Ta tâche est de produire un rapport bibliométrique structuré et professionnel de type HCERES pour l'équipe de recherche ACENTAURI à l'INRIA Sophia Antipolis, couvrant la période 2022–2026. Le rapport doit être rédigé au format Markdown.

Consignes :
- Utilise un ton formel et institutionnel approprié aux soumissions HCERES
- Structure le rapport avec des sections et sous-sections claires
- Inclus les données numériques et pourcentages des tableaux fournis
- Fournis des commentaires analytiques interprétant les tendances, pas seulement une liste de chiffres
- Mets en évidence les points forts et les axes d'amélioration
- Note explicitement les limites des données ou les réserves
- Inclus des tableaux au format Markdown là où c'est pertinent
- Le rapport doit être complet (2000–4000 mots)

═══════════════════════════════════════════════════════════════
DONNÉES BIBLIOMÉTRIQUES
═══════════════════════════════════════════════════════════════

### Indicateurs de synthèse
${csvToText(summary)}

### Production annuelle
${csvToText(annual)}

### Répartition par type de document
${csvToText(docType)}

### Auteurs (complet)
${csvToText(authors, 100)}

### Supports de publication (top 30)
${csvToText(venues, 30)}

### Résumé des collaborations
${csvToText(collabSummary)}

### Partenaires institutionnels (top 20)
${csvToText(partners, 20)}

### Pays collaborateurs
${csvToText(countries)}

### Indicateurs de science ouverte
${csvToText(openScience)}

### Disponibilité du texte intégral par année
${csvToText(annualFull)}

═══════════════════════════════════════════════════════════════
STRUCTURE DEMANDÉE
═══════════════════════════════════════════════════════════════

${reportStructure}

═══════════════════════════════════════════════════════════════
CONSIGNE FINALE
═══════════════════════════════════════════════════════════════

Rédige maintenant le rapport complet en suivant la structure ci-dessus. Chaque section doit contenir une analyse commentée, pas seulement des chiffres bruts.`;
}

// --- Store generated report ---
let generatedReport = '';

// --- UI Logic ---
document.addEventListener('DOMContentLoaded', () => {
  // Structure prompt elements
  const structureTextarea = document.getElementById('report-structure-textarea');
  const languageEl = document.getElementById('llm-language');
  const btnResetStructure = document.getElementById('btn-reset-structure');
  const btnExportPrompt = document.getElementById('btn-export-prompt');
  const btnPreviewPrompt = document.getElementById('btn-preview-prompt');
  const btnGenerateExport = document.getElementById('btn-generate-export');
  const exportStatusEl = document.getElementById('export-status');
  const promptModal = document.getElementById('prompt-preview-modal');
  const promptModalContent = document.getElementById('prompt-preview-content');
  const btnCloseModal = document.getElementById('btn-close-prompt-modal');

  // Report output elements
  const outputCard = document.getElementById('report-output-card');
  const renderedEl = document.getElementById('report-rendered');
  const rawEl = document.getElementById('report-raw');
  const btnCopy = document.getElementById('btn-copy-report');
  const btnDownload = document.getElementById('btn-download-md');
  const btnToggle = document.getElementById('btn-toggle-raw');

  if (!btnGenerateExport) return;

  // Initialize structure textarea with default
  if (structureTextarea) {
    structureTextarea.value = DEFAULT_REPORT_STRUCTURE;
  }

  // Reset structure to default
  if (btnResetStructure) {
    btnResetStructure.addEventListener('click', () => {
      structureTextarea.value = DEFAULT_REPORT_STRUCTURE;
      autoResizeTextarea();
      btnResetStructure.textContent = '✅ Réinitialisé !';
      setTimeout(() => { btnResetStructure.innerHTML = '🔄 Réinitialiser'; }, 1500);
    });
  }

  // Auto-resize textarea
  function autoResizeTextarea() {
    if (!structureTextarea) return;
    structureTextarea.style.height = 'auto';
    structureTextarea.style.height = Math.min(structureTextarea.scrollHeight, 500) + 'px';
  }
  if (structureTextarea) {
    structureTextarea.addEventListener('input', autoResizeTextarea);
    setTimeout(autoResizeTextarea, 100);
  }

  // === MAIN EXPORT BUTTON ===
  btnGenerateExport.addEventListener('click', async () => {
    const language = languageEl ? languageEl.value : 'fr';
    const structure = structureTextarea ? structureTextarea.value : DEFAULT_REPORT_STRUCTURE;

    btnGenerateExport.classList.add('loading');
    btnGenerateExport.disabled = true;
    exportStatusEl.textContent = '⏳ Collecte des données du dashboard...';
    exportStatusEl.className = 'generate-status';

    try {
      const fullPrompt = await buildFullPrompt(language, structure);

      // Download as .txt
      const blob = new Blob([fullPrompt], { type: 'text/plain;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `prompt_rapport_hceres_acentauri_${new Date().toISOString().slice(0, 10)}.txt`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      exportStatusEl.innerHTML = '✅ <strong>Prompt exporté !</strong> Envoyez ce fichier à Antigravity ou collez-le dans votre conversation pour que le rapport soit rédigé.';
      exportStatusEl.className = 'generate-status success';
    } catch (err) {
      exportStatusEl.textContent = `❌ Erreur : ${err.message}`;
      exportStatusEl.className = 'generate-status error';
    } finally {
      btnGenerateExport.classList.remove('loading');
      btnGenerateExport.disabled = false;
    }
  });

  // Preview full prompt in modal
  if (btnPreviewPrompt && promptModal) {
    btnPreviewPrompt.addEventListener('click', async () => {
      btnPreviewPrompt.classList.add('loading');
      const language = languageEl ? languageEl.value : 'fr';
      const structure = structureTextarea ? structureTextarea.value : DEFAULT_REPORT_STRUCTURE;
      const fullPrompt = await buildFullPrompt(language, structure);

      // Split into sections for display
      const sections = fullPrompt.split('═══════════════════════════════════════════════════════════════');
      let html = '';
      const sectionLabels = ['En-tête', 'INSTRUCTIONS', '', 'DONNÉES BIBLIOMÉTRIQUES', '', 'STRUCTURE DEMANDÉE', '', 'CONSIGNE FINALE', ''];

      sections.forEach((section, i) => {
        const trimmed = section.trim();
        if (!trimmed) return;
        const label = sectionLabels[i] || '';
        const isHeader = i === 0;
        const roleClass = isHeader ? 'system' : (label === 'DONNÉES BIBLIOMÉTRIQUES' ? 'data' : 'user');
        const icon = isHeader ? '📋' : (roleClass === 'data' ? '📊' : (label === 'INSTRUCTIONS' ? '🔧' : '📝'));

        html += `<div class="prompt-block prompt-${roleClass}">
          <div class="prompt-role">${icon} ${label || 'CONTENU'}</div>
          <pre class="prompt-text">${escapeHtml(trimmed)}</pre>
        </div>`;
      });

      promptModalContent.innerHTML = html;
      promptModal.classList.add('open');
      btnPreviewPrompt.classList.remove('loading');
    });

    if (btnCloseModal) {
      btnCloseModal.addEventListener('click', () => promptModal.classList.remove('open'));
    }
    promptModal.addEventListener('click', (e) => {
      if (e.target === promptModal) promptModal.classList.remove('open');
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && promptModal.classList.contains('open')) {
        promptModal.classList.remove('open');
      }
    });
  }

  // Export prompt as .txt (secondary button)
  if (btnExportPrompt) {
    btnExportPrompt.addEventListener('click', async () => {
      const language = languageEl ? languageEl.value : 'fr';
      const structure = structureTextarea ? structureTextarea.value : DEFAULT_REPORT_STRUCTURE;
      const fullPrompt = await buildFullPrompt(language, structure);

      const blob = new Blob([fullPrompt], { type: 'text/plain;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `prompt_rapport_hceres_acentauri_${new Date().toISOString().slice(0, 10)}.txt`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      btnExportPrompt.textContent = '✅ Exporté !';
      setTimeout(() => { btnExportPrompt.textContent = '⬇️ Exporter .txt'; }, 2000);
    });
  }

  // === REPORT DISPLAY (populated when Antigravity writes the report) ===
  // These buttons handle a report that gets loaded into the output card

  if (btnCopy) {
    btnCopy.addEventListener('click', async () => {
      if (!generatedReport) return;
      try {
        await navigator.clipboard.writeText(generatedReport);
        btnCopy.textContent = '✅ Copié !';
        setTimeout(() => { btnCopy.textContent = '📋 Copier'; }, 2000);
      } catch {
        const ta = document.createElement('textarea');
        ta.value = generatedReport;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        btnCopy.textContent = '✅ Copié !';
        setTimeout(() => { btnCopy.textContent = '📋 Copier'; }, 2000);
      }
    });
  }

  if (btnDownload) {
    btnDownload.addEventListener('click', () => {
      if (!generatedReport) return;
      const blob = new Blob([generatedReport], { type: 'text/markdown;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `rapport_hceres_acentauri_${new Date().toISOString().slice(0, 10)}.md`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    });
  }

  if (btnToggle) {
    let showingRaw = false;
    btnToggle.addEventListener('click', () => {
      showingRaw = !showingRaw;
      if (renderedEl) renderedEl.style.display = showingRaw ? 'none' : '';
      if (rawEl) rawEl.style.display = showingRaw ? '' : 'none';
      btnToggle.textContent = showingRaw ? '📄 Rendu' : '{ } Source';
    });
  }
});

// --- Utility ---
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// --- Public function to load a report into the UI (called externally) ---
function displayReport(markdownContent) {
  generatedReport = markdownContent;
  const outputCard = document.getElementById('report-output-card');
  const renderedEl = document.getElementById('report-rendered');
  const rawEl = document.getElementById('report-raw');
  if (outputCard) outputCard.style.display = '';
  if (renderedEl) renderedEl.innerHTML = marked.parse(markdownContent);
  if (rawEl) rawEl.textContent = markdownContent;
  if (outputCard) outputCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
}
