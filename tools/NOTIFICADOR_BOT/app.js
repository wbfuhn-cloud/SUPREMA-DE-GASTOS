
// Auto-initialize Lucide Icons on DOM changes (Fix v2.7.3: Infinite loop prevention)
if (typeof MutationObserver !== 'undefined' && document.body) {
    const observer = new MutationObserver((mutations) => {
        let shouldUpdate = false;
        for (let mutation of mutations) {
            for (let node of mutation.addedNodes) {
                if (node.nodeType === 1) { // Node.ELEMENT_NODE
                    if (node.hasAttribute && node.hasAttribute('data-lucide')) shouldUpdate = true;
                    else if (node.querySelector && node.querySelector('[data-lucide]')) shouldUpdate = true;
                }
            }
        }
        if (shouldUpdate && window.lucide) {
            observer.disconnect(); // Pausar para evitar loop infinito
            try { 
                lucide.createIcons(); 
                // Limpiar el atributo de los SVG generados para que no se vuelvan a procesar
                document.querySelectorAll('svg[data-lucide]').forEach(svg => {
                    svg.removeAttribute('data-lucide');
                });
            } catch (e) { /* iconos opcionales */ }
            observer.observe(document.body, { childList: true, subtree: true });
        }
    });
    try { observer.observe(document.body, { childList: true, subtree: true }); } catch (e) { /* noop */ }
}

const API_URL = "/api";

function escapeHtml(value) {
    const node = document.createElement('div');
    node.textContent = String(value ?? '');
    return node.innerHTML;
}

// Elements
const btnStart = document.getElementById("btn-start");
const btnStop = document.getElementById("btn-stop");
const btnClearCache = document.getElementById("btn-clear-cache");
const btnClearTicker = document.getElementById("btn-clear-ticker");
const sourceSelect = document.getElementById("source-select");
const workersSlider = document.getElementById("workers-slider");
const workersVal = document.getElementById("workers-val");
const useCacheChk = document.getElementById("use-cache");
const sourceSubtitle = document.getElementById("source-subtitle");
const marketStatus = document.getElementById("market-status");
const cacheStats = document.getElementById("cache-stats");
const progressBar = document.getElementById("progress-bar");
const progressText = document.getElementById("progress-text");

const tabBtns = document.querySelectorAll(".tab-btn[data-tab]");
const tabContents = document.querySelectorAll(".tab-content");
const btnPortfolioShortcut = document.getElementById("btn-portfolio-shortcut");

const volatilityTableBody = document.querySelector("#volatility-table tbody");
const gemsTableBody = document.querySelector("#gems-table tbody");
const riskOutput = document.getElementById("risk-output");
const detailsContent = document.getElementById("details-content");
const autoScanChk = document.getElementById("auto-scan");

const tslaMonitor = document.getElementById("tsla-monitor");
const tslaContent = document.getElementById("tsla-content");

// Null-safe stubs for removed general-tab elements
const filterViability = { value: 'TODAS', addEventListener: () => {} };
const searchTicker = { value: '', addEventListener: () => {} };

// State
let isScanning = false;
let statusInterval = null;
let autoScanInterval = null;
let allResults = [];
let selectedTickerData = null;

// El documento usa .page-content como scroller. Durante el movimiento se
// suspenden transiciones y sombras costosas; se restauran al quedar inactivo.
const pageScroller = document.querySelector('.page-content');
let scrollIdleTimer = null;
if (pageScroller) {
    pageScroller.addEventListener('scroll', () => {
        document.documentElement.classList.add('is-scrolling');
        if (scrollIdleTimer) clearTimeout(scrollIdleTimer);
        scrollIdleTimer = setTimeout(() => {
            document.documentElement.classList.remove('is-scrolling');
            scrollIdleTimer = null;
        }, 120);
    }, { passive: true });
}

function hasNumericValue(value) {
    return value !== null && value !== undefined && Number.isFinite(Number(value));
}

function quoteStatus(row) {
    const quote = row.Quote || row.quote;
    if (!quote || !quote.market_timestamp) {
        return { label: 'Datos sin timestamp', cssClass: 'stale', detail: 'Proveedor no identificado' };
    }
    const timestamp = new Date(quote.market_timestamp);
    const formatted = Number.isNaN(timestamp.getTime()) ? quote.market_timestamp : timestamp.toLocaleString();
    const quality = hasNumericValue(quote.quality_score) ? `${(Number(quote.quality_score) * 100).toFixed(0)}%` : 'N/D';
    return {
        label: quote.is_stale ? 'Datos vencidos' : 'Datos vigentes',
        cssClass: quote.is_stale ? 'stale' : 'fresh',
        detail: `${quote.provider || 'proveedor N/D'} · ${formatted} · calidad ${quality}`,
    };
}

function showToast(message, type = "info") {
    const region = document.getElementById("toast-region");
    if (!region) return;
    const toast = document.createElement("div");
    toast.className = `app-toast ${type}`;
    toast.setAttribute("role", type === "error" ? "alert" : "status");
    toast.textContent = message;
    region.appendChild(toast);
    setTimeout(() => toast.remove(), 4500);
}

function requestConfirmation(message) {
    const dialog = document.getElementById("app-confirm-dialog");
    const messageEl = document.getElementById("app-confirm-message");
    const accept = document.getElementById("app-confirm-accept");
    const cancel = document.getElementById("app-confirm-cancel");
    if (!dialog || !messageEl || !accept || !cancel || typeof dialog.showModal !== "function") {
        return Promise.resolve(false);
    }

    messageEl.textContent = message;
    dialog.showModal();
    cancel.focus();
    return new Promise(resolve => {
        const finish = value => {
            accept.removeEventListener("click", onAccept);
            cancel.removeEventListener("click", onCancel);
            dialog.removeEventListener("cancel", onCancel);
            if (dialog.open) dialog.close();
            resolve(value);
        };
        const onAccept = () => finish(true);
        const onCancel = event => { event.preventDefault(); finish(false); };
        accept.addEventListener("click", onAccept);
        cancel.addEventListener("click", onCancel);
        dialog.addEventListener("cancel", onCancel);
    });
}

function activateTab(tabId, button) {
    const panel = document.getElementById(tabId);
    if (!panel || !button) {
        showToast("La sección solicitada no está disponible.", "error");
        return false;
    }

    tabBtns.forEach(item => {
        const active = item === button;
        item.classList.toggle("active", active);
        item.setAttribute("aria-selected", String(active));
        item.tabIndex = active ? 0 : -1;
    });
    tabContents.forEach(content => content.classList.toggle("active", content === panel));
    return true;
}

// Initialization
document.addEventListener("DOMContentLoaded", async () => {
    // 1. Actualizar estadísticas iniciales
    updateCacheStats();
    
    // 2. Traer inmediatamente los resultados del servidor
    await fetchResults();

    // 3. Cargar estado de escaneo
    await checkScanStatus();
    
    // 4. El programador del servidor decide cuándo escanear para no contaminar
    // la evidencia con datos fuera de sesión.
    // Cargar portafolio desde la API (sincronizado con el bot)
    try {
        const res = await fetch(`${API_URL}/portfolio/config`);
        const data = await res.json();
        if (!res.ok || data.status === 'error') {
            throw new Error(data.message || `HTTP ${res.status}`);
        }
        renderPortfolioSnapshot(data.portfolio || {});
        if (data.sync && data.sync.backend === 'cloud' && !data.sync.synchronized) {
            showToast('Portafolio cargado desde respaldo local; la nube no está disponible.', 'warning');
        }
    } catch (e) {
        console.error("Error cargando portafolio:", e);
    }

    // 5. Cargar y analizar portafolio automáticamente al iniciar
    await Promise.all([analyzePortfolio(), loadMaturityStatus()]);
});

// Event Listeners (v2.7.1: guards null — un elemento faltante tumbaba todo el visor en blanco)
if (workersSlider && workersVal) workersSlider.addEventListener("input", (e) => { workersVal.textContent = e.target.value; });
if (sourceSelect && sourceSubtitle) sourceSelect.addEventListener("change", (e) => {
    try {
        const text = e.target.options[e.target.selectedIndex].text;
        sourceSubtitle.textContent = `${text} (OPTIMIZADO)`;
    } catch (err) { /* noop */ }
});

if (btnStart) btnStart.addEventListener("click", startScan);
if (btnStop) btnStop.addEventListener("click", stopScan);
if (btnClearCache) btnClearCache.addEventListener("click", () => clearCache("data"));
if (btnClearTicker) btnClearTicker.addEventListener("click", () => clearCache("tickers"));

// Portfolio elements
const btnAddPortfolio = document.getElementById("btn-add-portfolio");
const portTicker = document.getElementById("port-ticker");
const portQty = document.getElementById("port-qty");
const portPrice = document.getElementById("port-price");
const portfolioTbody = document.getElementById("portfolio-tbody");

if (btnAddPortfolio) {
    btnAddPortfolio.addEventListener("click", handleAddPortfolio);
}

// Navegación accesible y carga diferida de paneles.
tabBtns.forEach(btn => {
    btn.addEventListener("click", async () => {
        const tabId = btn.dataset.tab;
        if (!activateTab(tabId, btn)) return;
        if (tabId === 'ai-tab') {
            await Promise.all([loadLearnerStats(), loadLearnerHistory(), loadTransparencyStatus()]);
        }
    });
    btn.addEventListener("keydown", event => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        const buttons = Array.from(tabBtns);
        const current = buttons.indexOf(btn);
        let next = current;
        if (event.key === 'ArrowLeft') next = (current - 1 + buttons.length) % buttons.length;
        if (event.key === 'ArrowRight') next = (current + 1) % buttons.length;
        if (event.key === 'Home') next = 0;
        if (event.key === 'End') next = buttons.length - 1;
        buttons[next].focus();
        buttons[next].click();
    });
});

if (btnPortfolioShortcut) btnPortfolioShortcut.addEventListener("click", scrollToPortfolio);

const btnRefreshAi = document.getElementById("btn-refresh-ai");
if (btnRefreshAi) {
    btnRefreshAi.addEventListener("click", () => {
        loadLearnerStats();
        loadLearnerHistory();
        loadTransparencyStatus();
        loadMaturityStatus();
    });
}

async function loadMaturityStatus() {
    const banner = document.getElementById('maturity-banner');
    if (!banner) return;
    try {
        const response = await fetch(`${API_URL}/bolsa/maturity`);
        const data = await response.json();
        if (!response.ok || data.status !== 'ok') throw new Error(data.message || `HTTP ${response.status}`);
        const maturity = data.maturity || {};
        const phase = maturity.current_phase || {};
        const solidity = maturity.solidity || {};
        const evidence = maturity.evidence || {};
        const sessions = evidence.market_sessions || {};
        const signals = evidence.eligible_signals || {};
        const quality = evidence.data_quality || {};
        const qualityText = quality.average === null || quality.average === undefined
            ? 'Sin muestra actual'
            : `Calidad ${(Number(quality.average) * 100).toFixed(0)}% · ${quality.passing}/${quality.observed} aptos`;

        banner.dataset.level = solidity.level || 'EXPERIMENTAL';
        banner.classList.remove('is-loading');
        const title = document.getElementById('maturity-title');
        const solid = document.getElementById('maturity-solidity');
        const technical = document.getElementById('maturity-technical');
        const evidenceEl = document.getElementById('maturity-evidence');
        const paper = document.getElementById('maturity-paper');
        const next = document.getElementById('maturity-next');
        const nextDetail = document.getElementById('maturity-next-detail');
        const notice = document.getElementById('maturity-notice');
        if (title) title.textContent = `Fase ${phase.number ?? '—'} · ${phase.name || 'Estado no disponible'}`;
        if (solid) solid.textContent = `${solidity.label || 'Sin evaluar'} · ${solidity.score ?? 0}%`;
        if (technical) technical.textContent = `${maturity.technical?.completed ?? 0}/${maturity.technical?.total ?? 12} · ${maturity.technical?.label || ''}`;
        if (evidenceEl) evidenceEl.textContent = qualityText;
        if (paper) paper.textContent = `${sessions.current ?? 0}/${sessions.required ?? 60} sesiones · ${signals.current ?? 0}/${signals.required ?? 300} señales`;
        if (next) next.textContent = maturity.next_step?.label || 'Completar gates pendientes';
        if (nextDetail) nextDetail.textContent = maturity.next_step?.detail || '';
        if (notice) notice.textContent = `${maturity.notice || ''} Dinero real: ${solidity.real_money_enabled ? 'habilitado' : 'NO habilitado'}.`;
    } catch (error) {
        banner.dataset.level = 'EXPERIMENTAL';
        const title = document.getElementById('maturity-title');
        const next = document.getElementById('maturity-next');
        if (title) title.textContent = 'Fase no verificable';
        if (next) next.textContent = 'Restablecer el diagnóstico antes de avanzar';
        console.error('Error loading maturity status', error);
    }
}

const btnFeedbackBad = document.getElementById("btn-feedback-bad");
const btnFeedbackGood = document.getElementById("btn-feedback-good");

async function submitStructuredFeedback(feedback) {
    if (!selectedTickerData) return;
    const ticker = selectedTickerData.Ticker;
    const predictionId = selectedTickerData.Prediction_IDs?.['5'];
    const reason = document.getElementById('feedback-reason')?.value || 'other';
    if (!predictionId) {
        showToast("Esta observación heredada no tiene una predicción auditable.", "error");
        return;
    }
    const label = feedback === 'positive' ? 'útil' : 'no útil';
    if (!await requestConfirmation(`¿Registrar la recomendación de ${ticker} como ${label}?`)) return;
    try {
        const response = await fetch(`${API_URL}/learner/feedback`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                prediction_id: predictionId,
                feedback,
                reason,
                user_id: 'local_user',
                user_role: 'owner'
            })
        });
        const data = await response.json();
        if (!response.ok || data.status !== 'ok') throw new Error(data.message || `HTTP ${response.status}`);
        showToast(`Feedback auditable registrado para ${ticker}.`, "success");
        [btnFeedbackBad, btnFeedbackGood].forEach(button => {
            if (button) button.disabled = true;
        });
    } catch (e) {
        console.error("Error enviando feedback", e);
        showToast("No fue posible registrar el feedback.", "error");
    }
}

if (btnFeedbackBad) btnFeedbackBad.addEventListener("click", () => submitStructuredFeedback('negative'));
if (btnFeedbackGood) btnFeedbackGood.addEventListener("click", () => submitStructuredFeedback('positive'));

async function loadLearnerStats() {
    const accuracyEl = document.getElementById('ai-accuracy');
    const avgEl = document.getElementById('ai-avg-change');
    const verifiedEl = document.getElementById('ai-verified');
    const adjustmentsEl = document.getElementById('ai-adjustments');
    [accuracyEl, avgEl, verifiedEl, adjustmentsEl].forEach(el => { if (el) el.textContent = '…'; });
    try {
        const res = await fetch(`${API_URL}/learner/stats`);
        const data = await res.json();
        if (!res.ok || data.status !== 'ok') throw new Error(data.message || `HTTP ${res.status}`);
        if (data.status === 'ok') {
            const hasVerified = Number(data.stats.verified) > 0;
            accuracyEl.textContent = hasVerified && data.stats.accuracy_pct !== null ? `${data.stats.accuracy_pct}%` : 'N/D';
            
            const avg = data.stats.avg_change_1d;
            avgEl.textContent = hasVerified ? `${avg > 0 ? '+' : ''}${avg}%` : 'N/D';
            avgEl.style.color = avg > 0 ? 'var(--success-color)' : (avg < 0 ? 'var(--danger-color)' : 'white');
            
            verifiedEl.textContent = data.stats.verified;
            adjustmentsEl.textContent = data.stats.total_adjustments;
        }

        // Consultar estado de Machine Learning
        const mlRes = await fetch(`${API_URL}/ml/status`);
        const mlData = await mlRes.json();
        if (mlData.status === 'ok' && mlData.ml && mlData.ml.trained) {
            const metrics = mlData.ml.metrics;
            const mlAccEl = document.getElementById('ai-accuracy');
            if (mlAccEl && metrics.full_precision) {
                mlAccEl.title = `Modelo ML GradientBoosting: ${metrics.samples_total} muestras | AUC: ${metrics.auc_score}%`;
            }
        } else if (mlData.status === 'ok' && mlData.ml) {
            accuracyEl.title = `Modelo no aprobado para producción: ${mlData.ml.degraded_reason || 'sin validación temporal'}. Se usa únicamente el motor heurístico.`;
        }
    } catch (e) {
        console.error("Error loading learner stats", e);
        [accuracyEl, avgEl, verifiedEl, adjustmentsEl].forEach(el => { if (el) el.textContent = 'Error'; });
        showToast("No fue posible cargar las métricas de aprendizaje.", "error");
    }
}

async function loadTransparencyStatus() {
    const panel = document.getElementById('ai-transparency-panel');
    if (!panel) return;
    try {
        const response = await fetch(`${API_URL}/bolsa/transparency`);
        const data = await response.json();
        if (!response.ok || data.status !== 'ok') throw new Error(data.message || `HTTP ${response.status}`);
        const ai = data.adaptive_ai || {};
        const paper = data.paper_trading || {};
        const modules = ai.modules || {};
        const metrics = paper.metrics || {};
        panel.innerHTML = `
            <h3 id="ai-transparency-title">Estado operativo y evidencia</h3>
            <div class="transparency-grid">
                <div><strong>Operación</strong><span>${escapeHtml(ai.operational_state || 'N/D')}</span></div>
                <div><strong>Heurística</strong><span>${escapeHtml(modules.heuristic || 'N/D')}</span></div>
                <div><strong>ML</strong><span>${escapeHtml(modules.ml || 'N/D')}</span></div>
                <div><strong>Fourier</strong><span>${escapeHtml(modules.fourier || 'N/D')}</span></div>
                <div><strong>Último entrenamiento</strong><span>${escapeHtml(ai.last_training || 'N/D')}</span></div>
                <div><strong>Predicciones verificadas</strong><span>${escapeHtml(ai.verified_predictions ?? 'N/D')}</span></div>
                <div><strong>Paper trading</strong><span>${escapeHtml(metrics.market_sessions ?? 0)} sesiones · ${escapeHtml(metrics.eligible_signals ?? 0)} señales</span></div>
                <div><strong>Gate</strong><span>${escapeHtml(paper.approval?.decision || 'N/D')}</span></div>
            </div>
            <p><strong>Razón de degradación:</strong> ${escapeHtml(ai.degradation_reason || 'N/D')}</p>
            <p class="financial-disclaimer">Análisis educativo. No garantiza resultados ni constituye asesoría financiera.</p>`;
    } catch (error) {
        panel.innerHTML = `<h3 id="ai-transparency-title">Estado operativo y evidencia</h3><p class="signal-blocked">No disponible: ${escapeHtml(error.message)}</p>`;
    }
}

async function loadLearnerHistory() {
    const tbody = document.getElementById('ai-history-tbody');
    if (!tbody) return;
    
    tbody.innerHTML = `<tr><td colspan="6"><i data-lucide="loader" class="lucide-spin"></i> Cargando historial...</td></tr>`;
    try {
        const form = document.getElementById('ai-history-filters');
        const query = form ? new URLSearchParams(new FormData(form)).toString() : '';
        const res = await fetch(`${API_URL}/learner/history${query ? `?${query}` : ''}`);
        const data = await res.json();
        if (data.status === 'ok') {
            tbody.innerHTML = '';
            if (data.history.length === 0) {
                tbody.innerHTML = `<tr class="empty-row"><td colspan="6">No hay historial verificado aún.</td></tr>`;
                return;
            }
            
            data.history.forEach(row => {
                const tr = document.createElement('tr');
                const outcome = row.outcome;
                let evalBadge = "neutro", evalText = "Pendiente";
                if (outcome === 'COMPRA_EXITOSA' || outcome === 'SALIDA_CORRECTA') {
                    evalBadge = "alta"; evalText = "🟢 Acertó";
                } else if (outcome === 'COMPRA_FALLIDA' || outcome === 'SALIDA_INCORRECTA') {
                    evalBadge = "evitar"; evalText = "🔴 Falló";
                } else if (row.status === 'IRRECOVERABLE') {
                    evalBadge = "evitar"; evalText = "Irrecuperable";
                } else if (outcome === 'NEUTRAL') {
                    evalText = "Neutral";
                }
                
                const change = row.change_pct_1d !== null ? `${row.change_pct_1d > 0 ? '+' : ''}${row.change_pct_1d.toFixed(2)}%` : '--';
                const changeColor = row.change_pct_1d > 0 ? 'var(--success-color)' : (row.change_pct_1d < 0 ? 'var(--danger-color)' : 'white');
                
                tr.innerHTML = `
                    <td>${new Date(row.scan_date).toLocaleString()} · ${row.horizon_sessions}s</td>
                    <td><strong>${row.ticker}</strong></td>
                    <td>${row.score.toFixed(1)}</td>
                    <td>$${row.price_at_rec.toFixed(2)}</td>
                    <td style="color:${changeColor}; font-weight:bold;">${change}</td>
                    <td><span class="badge ${evalBadge}">${evalText}</span></td>
                `;
                tbody.appendChild(tr);
            });
        }
    } catch (e) {
        console.error("Error loading learner history", e);
        tbody.innerHTML = `<tr><td colspan="6" style="color:var(--danger-color)">Error al cargar historial</td></tr>`;
    }
}

const aiHistoryFilters = document.getElementById('ai-history-filters');
if (aiHistoryFilters) aiHistoryFilters.addEventListener('submit', event => {
    event.preventDefault();
    loadLearnerHistory();
});

filterViability.addEventListener("change", renderTables);
searchTicker.addEventListener("input", renderTables);

document.querySelectorAll(".risk-inputs input").forEach(input => {
    input.addEventListener("input", () => {
        if (selectedTickerData) calculateRisk(selectedTickerData);
    });
});

if (autoScanChk) autoScanChk.addEventListener("change", (e) => {
    // El auto-scan ahora se gestiona principalmente en el servidor
    // pero permitimos al usuario forzar un inicio si lo desea
    if(e.target.checked && !isScanning) {
        startScan();
    }
});

// API Calls
async function updateCacheStats() {
    try {
        const res = await fetch(`${API_URL}/cache/stats`);
        const data = await res.json();
        const dCache = data.data_cache;
        if (cacheStats) cacheStats.innerHTML = `<i data-lucide="zap"></i> Caché: ${dCache.total_tickers} stocks | ${dCache.total_size_mb.toFixed(1)} MB | Listas: ${data.ticker_cache.cached_sources}`;
    } catch (e) {
        console.error("Error fetching cache stats", e);
    }
}

async function clearCache(target) {
    if(!await requestConfirmation(`¿Limpiar la caché de ${target}?`)) return;
    try {
        const response = await fetch(`${API_URL}/cache/clear`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ target })
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        updateCacheStats();
        showToast("Caché limpiada correctamente.", "success");
    } catch (e) {
        console.error("Error clearing cache", e);
        showToast("No fue posible limpiar la caché.", "error");
    }
}

async function startScan() {
    try {
        // sp500_nasdaq = combinar ambas fuentes en el backend
        let source = sourceSelect.value;
        if (source === 'sp500_nasdaq') source = 'sp500_nasdaq';

        const res = await fetch(`${API_URL}/scan/start`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                source: source,
                max_workers: parseInt(workersSlider.value),
                use_cache: useCacheChk.checked
            })
        });
        
        if(res.ok) {
            btnStart.disabled = true;
            btnStop.disabled = false;
            allResults = [];
            renderTables();
            isScanning = true;
            startStatusPolling();
        }
    } catch (e) {
        console.error("Error starting scan", e);
    }
}

async function stopScan() {
    try {
        await fetch(`${API_URL}/scan/stop`, { method: "POST" });
    } catch (e) {
        console.error("Error stopping scan", e);
    }
}

async function handleAddPortfolio() {
    const ticker = portTicker.value.trim().toUpperCase();
    const qty = parseFloat(portQty.value);
    const price = parseFloat(portPrice.value);
    
    if (!ticker || isNaN(qty) || isNaN(price)) {
        showToast("Completa todos los campos correctamente.", "error");
        return;
    }
    
    btnAddPortfolio.disabled = true;
    try {
        const response = await fetch(`${API_URL}/portfolio/update`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ticker, qty, price })
        });
        const data = await response.json();
        if (!response.ok || data.status !== 'ok') throw new Error(data.message || `HTTP ${response.status}`);
        portTicker.value = "";
        portPrice.value = "";
        await analyzePortfolio();
        const cloudOk = data.sync && data.sync.synchronized;
        showToast(cloudOk
            ? `${ticker} quedó guardado y sincronizado en la nube.`
            : `${ticker} quedó guardado sólo en este dispositivo.`, cloudOk ? "success" : "warning");
    } catch (e) {
        console.error("Error adding to portfolio", e);
        showToast(`No fue posible guardar ${ticker}.`, "error");
    }
    btnAddPortfolio.disabled = false;
}

function renderPortfolioSnapshot(portfolio) {
    if (!portfolioTbody || !portfolio || Array.isArray(portfolio)) return;
    const entries = Object.entries(portfolio);
    if (entries.length === 0) return;
    portfolioTbody.innerHTML = '';
    entries.forEach(([ticker, position]) => {
        const qty = Number(position?.qty) || 0;
        const entry = Number(position?.avg_price) || 0;
        const tr = document.createElement('tr');
        tr.dataset.portfolioSnapshot = 'true';
        tr.innerHTML = `
            <td><strong style="font-size:16px;color:var(--text-primary);">${escapeHtml(ticker)}</strong></td>
            <td><strong>${qty}</strong> acc<br><small>@ $${entry.toFixed(2)} USD</small></td>
            <td colspan="3" style="color:var(--text-secondary);">Posición guardada · actualizando cotización y análisis…</td>
            <td></td>`;
        portfolioTbody.appendChild(tr);
    });
    const totalCountEl = document.getElementById('port-total-count');
    if (totalCountEl) totalCountEl.textContent = `${entries.length} activos`;
}

async function analyzePortfolio() {
    if (!portfolioTbody) return;
    const hasVisibleHoldings = Boolean(portfolioTbody.querySelector('tr[data-portfolio-snapshot], tr[data-portfolio-analyzed]'));
    portfolioTbody.setAttribute('aria-busy', 'true');
    if (!hasVisibleHoldings) {
        portfolioTbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding: 28px; color:var(--text-secondary);"><i class="fa-solid fa-spinner fa-spin" style="margin-right:8px; color:var(--primary-color)"></i> Analizando Cartera en tiempo real...</td></tr>`;
    }
    
    try {
        const res = await fetch(`${API_URL}/portfolio/analyze`);
        const data = await res.json();
        if (!res.ok) throw new Error(data.message || `HTTP ${res.status}`);
        
        if (data.status === 'ok') {
            portfolioTbody.innerHTML = '';
            const totalCountEl = document.getElementById('port-total-count');
            const totalPlEl = document.getElementById('port-total-pl');

            if (!data.results || data.results.length === 0) {
                portfolioTbody.innerHTML = `<tr class="empty-row"><td colspan="6" style="text-align:center; padding: 32px; color:var(--text-muted);">No tienes posiciones registradas. Agrega tus tickers arriba para que el asesor las monitoree en tiempo real.</td></tr>`;
                if (totalCountEl) totalCountEl.textContent = '0 activos';
                if (totalPlEl) totalPlEl.textContent = '$0.00 USD';
                return;
            }

            if (totalCountEl) totalCountEl.textContent = `${data.results.length} activos`;
            
            let totalPlUsd = 0;
            let totalCostUsd = 0;
            let hasValidCost = false;

            data.results.forEach(row => {
                const tr = document.createElement('tr');
                tr.dataset.portfolioAnalyzed = 'true';
                const positionStatus = row.portfolio_status || {
                    color: 'yellow', label: 'ESPERAR / VALIDAR',
                    reason: row.error || 'No existe evidencia suficiente.', confidence: 'insuficiente'
                };
                tr.classList.add(`portfolio-row-${positionStatus.color || 'yellow'}`);
                if (row.error && !hasNumericValue(row.price)) {
                    tr.innerHTML = `
                        <td><strong style="font-size:15px; color:var(--text-primary);">${escapeHtml(row.ticker)}</strong></td>
                        <td><strong>${escapeHtml(row.qty ?? '—')}</strong> acc<br><small>@ $${hasNumericValue(row.entry_price) ? Number(row.entry_price).toFixed(2) : '—'} USD</small></td>
                        <td style="color:var(--text-secondary);">N/D</td>
                        <td><span class="portfolio-signal ${escapeHtml(positionStatus.color)}">${escapeHtml(positionStatus.label)}</span><small class="portfolio-signal-reason">${escapeHtml(positionStatus.reason)}</small></td>
                        <td style="color:var(--text-secondary);">No calculable</td>
                        <td style="text-align:center;">
                            <button onclick="removePortfolioItem('${escapeHtml(row.ticker)}')" class="btn sm-btn danger-btn" title="Eliminar"><i class="fa-solid fa-trash-can"></i></button>
                        </td>
                    `;
                } else {
                    let badgeClass = "neutro";
                    const verdictUpper = String(row.verdict || "").toUpperCase();
                    if (verdictUpper.includes("COMPRA") || verdictUpper.includes("AUMENTA")) badgeClass = "alta";
                    else if (verdictUpper.includes("MANTEN") || verdictUpper.includes("MEDIA")) badgeClass = "moderado";
                    else if (verdictUpper.includes("VENTA") || verdictUpper.includes("EVITAR") || verdictUpper.includes("REDUCIR")) badgeClass = "evitar";
                    
                    const plPct = Number(row.pl_pct) || 0;
                    const plVal = Number(row.pl_val) || 0;
                    const plMxn = Number(row.pl_mxn) || 0;
                    const plColor = plPct >= 0 ? "var(--success-color)" : "var(--danger-color)";
                    const plSign = plPct >= 0 ? "+" : "";

                    if (row.pl_val !== undefined && row.entry_price > 0 && row.qty > 0 && row.pnl_reliable !== false) {
                        totalPlUsd += plVal;
                        totalCostUsd += (Number(row.entry_price) * Number(row.qty));
                        hasValidCost = true;
                    }

                    const levFlag = row.is_leveraged ? ' <span class="badge evitar" style="font-size:10px; margin-left:6px; letter-spacing:0.4px;">APALANCADO</span>' : '';
                    const reasons = Array.isArray(row.reasons) ? [...row.reasons] : [];
                    if (row.error) reasons.unshift(row.error);
                    const reasonsList = reasons.join(" • ");
                    const pnlValidationLabel = row.pnl_reliable === false ? '<span class="pnl-unverified">NO VALIDADO</span>' : '';

                    tr.innerHTML = `
                        <td>
                            <div style="display:flex; align-items:center; gap:8px;">
                                <strong style="font-size:16px; letter-spacing:-0.3px; color:var(--text-primary);">${escapeHtml(row.ticker)}</strong>
                                ${levFlag}
                            </div>
                        </td>
                        <td>
                            <div style="font-weight:700; color:var(--text-primary); font-size:15px;">${row.qty} <span style="font-size:12px; color:var(--text-secondary); font-weight:500;">acc</span></div>
                            <small style="color:var(--text-muted); font-size:12px;">@ $${row.entry_price ? Number(row.entry_price).toFixed(2) : '0.00'} USD</small>
                        </td>
                        <td>
                            <div style="font-weight:800; font-size:15px; color:var(--text-primary);">$${row.price ? Number(row.price).toFixed(2) : '0.00'} <small style="font-size:11px; color:var(--text-secondary);">USD</small></div>
                            <small style="color:var(--text-secondary); font-weight:600;">$${row.price_mxn ? Number(row.price_mxn).toFixed(2) : '0.00'} MXN</small>
                        </td>
                        <td>
                            <div style="display:flex; flex-direction:column; gap:4px; max-width:320px;">
                                <span class="portfolio-signal ${escapeHtml(positionStatus.color)}">${escapeHtml(positionStatus.label)}</span>
                                <span class="portfolio-signal-reason">${escapeHtml(positionStatus.reason)}${positionStatus.confidence ? ` · Confianza ${escapeHtml(positionStatus.confidence)}` : ''}</span>
                                ${row.verdict ? `<span class="badge ${badgeClass}" style="width:fit-content;font-size:10px;padding:3px 8px;">Motor: ${escapeHtml(row.verdict)}</span>` : ''}
                                ${reasonsList ? `<span style="font-size:11px; color:var(--text-secondary); line-height:1.35; white-space:normal;" title="${escapeHtml(reasonsList)}">${escapeHtml(reasonsList)}</span>` : ''}
                            </div>
                        </td>
                        <td style="color: ${plColor}; font-weight: 800; font-size:15px;">
                            ${plSign}${plPct.toFixed(2)}%
                            <div style="font-size:12px; font-weight:700; opacity:0.9; margin-top:3px;">
                                ${plSign}$${plVal.toFixed(2)} USD
                                ${plMxn ? ` <span style="font-weight:500; opacity:0.8;">(${plSign}$${plMxn.toFixed(2)} MXN)</span>` : ''}
                            </div>
                            ${pnlValidationLabel}
                        </td>
                        <td style="text-align:center;">
                            <button onclick="removePortfolioItem('${escapeHtml(row.ticker)}')" class="btn sm-btn danger-btn" title="Eliminar ${escapeHtml(row.ticker)} de la cartera" style="padding:8px 12px; border-radius:10px;">
                                <i class="fa-solid fa-trash-can"></i>
                            </button>
                        </td>
                    `;

                    // Click en fila para ver desglose en panel superior
                    tr.style.cursor = "pointer";
                    tr.title = "Haz clic para ver análisis en el panel superior";
                    tr.addEventListener("click", (e) => {
                        if (e.target.closest('button')) return;
                        inspectPortfolioTicker(row);
                    });
                }
                portfolioTbody.appendChild(tr);
            });

            if (totalPlEl) {
                if (hasValidCost && totalCostUsd > 0) {
                    const totalPlPct = (totalPlUsd / totalCostUsd) * 100;
                    const sign = totalPlUsd >= 0 ? "+" : "";
                    const color = totalPlUsd >= 0 ? "var(--success-color)" : "var(--danger-color)";
                    totalPlEl.innerHTML = `<span style="color:${color}; font-weight:800;">${sign}$${totalPlUsd.toFixed(2)} USD (${sign}${totalPlPct.toFixed(2)}%)</span>`;
                } else {
                    totalPlEl.innerHTML = `<span style="color:var(--text-primary); font-weight:700;">$${totalPlUsd.toFixed(2)} USD</span>`;
                }
            }
        } else {
            throw new Error(data.message || 'No se pudo analizar el portafolio');
        }
    } catch (e) {
        console.error("Error analyzing portfolio", e);
        if (!hasVisibleHoldings) {
            portfolioTbody.innerHTML = `<tr><td colspan="6" style="color:var(--danger-color); padding: 24px; text-align:center;">No se pudo cargar el portafolio. ${escapeHtml(e.message || 'Error de conexión')}</td></tr>`;
        } else {
            showToast(`Tus posiciones siguen guardadas; no se pudo actualizar su análisis.`, "error");
        }
    } finally {
        portfolioTbody.removeAttribute('aria-busy');
    }
}

function scrollToPortfolio() {
    const el = document.getElementById("portfolio-section");
    if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        el.classList.add("highlight-pulse");
        setTimeout(() => el.classList.remove("highlight-pulse"), 1600);
    }
}
window.scrollToPortfolio = scrollToPortfolio;

function inspectPortfolioTicker(row) {
    const existing = allResults.find(r => r.Ticker === row.ticker);
    if (existing) {
        selectTicker(existing, null);
    } else {
        selectTicker({
            Ticker: row.ticker,
            Price: row.price,
            Price_MXN: row.price_mxn,
            Viabilidad: row.verdict || 'Portafolio',
            Score: 70,
            ML_Score: 70,
            ML_Confidence: 'Cartera',
            Score_Tech: 28,
            Score_Fund: 27,
            Score_Liq: 15,
            RSI: row.rsi,
            Is_Leveraged: row.is_leveraged,
            Nota: Array.isArray(row.reasons) ? row.reasons.join(', ') : 'Posición activa en portafolio'
        }, null);
    }
    const details = document.querySelector(".ticker-details");
    if (details) {
        details.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}
window.inspectPortfolioTicker = inspectPortfolioTicker;

async function removePortfolioItem(ticker) {
    if (!await requestConfirmation(`¿Eliminar ${ticker} del portafolio?`)) return;
    try {
        // En server.py creamos una lógica para borrar o actualizar
        const response = await fetch(`${API_URL}/portfolio/config`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ 
                action: 'remove', 
                ticker: ticker 
            })
        });
        const data = await response.json();
        if (!response.ok || data.status !== 'ok') throw new Error(data.message || `HTTP ${response.status}`);
        analyzePortfolio();
        const cloudOk = data.sync && data.sync.synchronized;
        showToast(cloudOk
            ? `${ticker} se eliminó y el cambio se sincronizó en la nube.`
            : `${ticker} se eliminó sólo en este dispositivo.`, cloudOk ? "success" : "warning");
    } catch (e) {
        console.error("Error removing portfolio item", e);
        showToast(`No fue posible eliminar ${ticker}.`, "error");
    }
}

function startStatusPolling() {
    if (statusInterval) return;
    statusInterval = setInterval(checkScanStatus, 1000);
}

async function checkScanStatus() {
    try {
        const res = await fetch(`${API_URL}/scan/status`);
        const data = await res.json();
        
        if (progressBar) progressBar.style.width = `${(data.progress || 0) * 100}%`;
        if (progressText) progressText.textContent = data.message || '';
        const automation = data.automation || {};
        const autoLabel = document.getElementById('auto-scan-label');
        if (autoScanChk) autoScanChk.checked = automation.enabled !== false;
        if (autoLabel) {
            const state = automation.scheduler_active ? 'ACTIVO' : 'INICIANDO';
            const market = automation.market_open ? 'mercado abierto' : 'esperando apertura';
            autoLabel.innerHTML = `<i class="fa-solid fa-robot"></i> Auto-Scan ${state} · ${market}`;
            autoLabel.title = automation.schedule || 'Programador automático del servidor';
        }
        
        if (!data.is_scanning && isScanning) {
            // Scan just finished
            isScanning = false;
            clearInterval(statusInterval);
            statusInterval = null;
            btnStart.disabled = false;
            btnStop.disabled = true;
            fetchResults();
            updateCacheStats();
        } else if (data.is_scanning) {
            isScanning = true;
            btnStart.disabled = true;
            btnStop.disabled = false;
            startStatusPolling(); // Asegurar que estamos polleando si está activo
        } else if (!data.is_scanning && !isScanning && allResults.length === 0) {
             // Si no hay resultados cargados pero hay disponibles en el servidor, traerlos
             if (data.results_count > 0) {
                 await fetchResults();
             }
        }
    } catch (e) {
        console.error("Error checking status", e);
    }
}

async function fetchResults() {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);
    try {
        const res = await fetch(`${API_URL}/scan/results`, { signal: controller.signal });
        clearTimeout(timeoutId);
        const data = await res.json();
        
        allResults = data.results || [];
        updateMarketContext(data.market_context);
        renderTables();
        await loadMaturityStatus();
    } catch (e) {
        clearTimeout(timeoutId);
        console.error("Error fetching results", e);
        if (e.name === 'AbortError') {
            const errDiv = document.createElement('div');
            errDiv.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%, -50%);background:#1f2937;color:#f87171;padding:20px;border-radius:12px;z-index:9999;box-shadow:0 10px 25px rgba(0,0,0,0.5);text-align:center;';
            errDiv.innerHTML = `<h3><i class="fa-solid fa-triangle-exclamation"></i> Timeout</h3>
                                <p>Servidor disponible, motor de Bolsa no responde a /api/scan/results en 5s.</p>
                                <button onclick="location.reload()" class="btn primary-btn" style="margin-top:15px">Reintentar</button>`;
            document.body.appendChild(errDiv);
        }
    }
}

// UI Rendering
function updateMarketContext(ctx) {
    if (!ctx || !ctx.regime) return;
    const regime = String(ctx.regime);
    let icon = "globe", colorClass = "neutral";
    if (regime.includes("ALCISTA")) { icon = "arrow-trend-up"; colorClass = "alcista"; }
    else if (regime.includes("BAJISTA")) { icon = "arrow-trend-down"; colorClass = "bajista"; }

    if (!marketStatus) return;
    marketStatus.innerHTML = `
        <span class="status-indicator ${colorClass}">
            <i class="fa-solid fa-${icon}"></i> ${regime} | VIX: ${ctx.vix ?? '?'} | SPY vs SMA200: ${ctx.spy_vs_sma200 ?? '?'}%
        </span>
    `;
}

function getBadgeClass(viability) {
    if (viability === undefined || viability === null) return "evitar";
    viability = String(viability);
    if (viability.includes("EXCELENTE")) return "alta";
    if (viability.includes("BUENA")) return "moderado";
    if (viability.includes("MODERADA")) return "neutro";
    return "evitar";
}

let currentViewMode = 'cards';

function switchViewMode(mode) {
    currentViewMode = mode;
    const btnCards = document.getElementById('btn-view-cards');
    const btnTable = document.getElementById('btn-view-table');
    const cardsVolContainer = document.getElementById('volatility-cards-container');
    const tableVolContainer = document.getElementById('volatility-table-container');
    const cardsGemsContainer = document.getElementById('gems-cards-container');
    const tableGemsContainer = document.getElementById('gems-table-container');

    if (btnCards) btnCards.classList.toggle('active', mode === 'cards');
    if (btnTable) btnTable.classList.toggle('active', mode === 'table');

    if (cardsVolContainer && tableVolContainer) {
        cardsVolContainer.style.display = (mode === 'cards') ? 'grid' : 'none';
        tableVolContainer.style.display = (mode === 'table') ? 'block' : 'none';
    }
    if (cardsGemsContainer && tableGemsContainer) {
        cardsGemsContainer.style.display = (mode === 'cards') ? 'grid' : 'none';
        tableGemsContainer.style.display = (mode === 'table') ? 'block' : 'none';
    }

    renderTables();
}

function renderGBMCards(container, items) {
    if (!container) return;
    container.innerHTML = "";
    if (!items || items.length === 0) {
        container.innerHTML = `<div class="placeholder-text" style="grid-column: 1/-1; padding: 40px; text-align: center;">No hay datos para mostrar en este escaneo.</div>`;
        return;
    }

    items.forEach(row => {
        const card = document.createElement("div");
        card.className = "gbm-stock-card";
        card.onclick = () => selectTicker(row, card);
        
        const badgeClass = getBadgeClass(row.Viabilidad);
        const vol = row.Volatility_Percent ? `${row.Volatility_Percent.toFixed(2)}%` : '0%';
        const levWarning = row.Is_Leveraged ? '<span class="badge evitar" style="font-size:9px;margin-left:4px;">APALANCADO</span>' : '';
        const hasAiConfidence = row.AI_Confidence_Available === true && hasNumericValue(row.AI_Confidence);
        const aiConf = hasAiConfidence ? `${Number(row.AI_Confidence).toFixed(0)}%` : 'N/D';
        const aiConfClass = !hasAiConfidence ? 'neutro' : (row.AI_Confidence > 75) ? 'alta' : (row.AI_Confidence > 50) ? 'media' : 'baja';
        const dataStatus = quoteStatus(row);

        card.innerHTML = `
            <div class="gbm-card-header">
                <div>
                    <div class="gbm-ticker">${row.Ticker}${levWarning}</div>
                    <div class="gbm-company">${row.Nombre || row.Category || 'Acción / Asset'}</div>
                </div>
                <div class="gbm-price-block">
                    <div class="gbm-price">$${row.Price.toFixed(2)}</div>
                    <div class="gbm-change ${(row.Volatility_Percent || 0) >= 0 ? 'pos' : 'neg'}">
                        ${(row.Volatility_Percent || 0) >= 0 ? '▲' : '▼'} ${vol}
                    </div>
                </div>
            </div>

            <div class="gbm-card-metrics">
                <div class="gbm-metric-item">
                    <span>Viabilidad</span>
                    <span><span class="badge ${badgeClass}">${row.Viabilidad}</span></span>
                </div>
                <div class="gbm-metric-item">
                    <span>Confianza IA</span>
                    <span><span class="ml-confidence-pill ${aiConfClass}">${aiConf}</span></span>
                </div>
                <div class="gbm-metric-item">
                    <span>RSI</span>
                    <span>${row.RSI || 'N/A'}</span>
                </div>
                <div class="gbm-metric-item">
                    <span>ATR (MXN)</span>
                    <span>$${row.ATR_MXN?.toFixed(2) || '0'}</span>
                </div>
            </div>

            <div style="font-size: 11px; color: var(--text-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; padding-top: 4px; border-top: 1px solid var(--glass-border);">
                <i class="fa-solid fa-circle-info" style="color: #0052FF;"></i> ${row.Nota || 'Sugerencia de entrada IA'}
            </div>
            <div class="data-freshness ${dataStatus.cssClass}" title="${escapeHtml(dataStatus.detail)}">
                ${dataStatus.label} · ${escapeHtml(dataStatus.detail)}
            </div>
        `;

        container.appendChild(card);
    });
}

function renderTables() {
    // v2.7.1: si faltan los tbody (HTML parcial), no tumbar el visor
    if (!volatilityTableBody || !gemsTableBody) return;
    const filter = filterViability.value;
    const search = searchTicker.value.toUpperCase();
    
    let filtered = allResults;
    if (filter !== "TODAS") {
        filtered = filtered.filter(r => r.Viabilidad === filter);
    }
    if (search) {
        filtered = filtered.filter(r => r.Ticker.toUpperCase().includes(search));
    }
    

    // Volatility Table (Sorted by Viability then Volatility)
    volatilityTableBody.innerHTML = "";
    
    const viabilityPriority = {
        "🟢 EXCELENTE": 100,
        "🟡 BUENA": 80,
        "🟠 MODERADA": 50,
        "🔴 EVITAR": 0,
        "TODAS": 0
    };

    const volSorted = [...allResults].sort((a,b) => {
        const pA = viabilityPriority[a.Viabilidad] || 0;
        const pB = viabilityPriority[b.Viabilidad] || 0;
        if (pA !== pB) return pB - pA;
        return (b.Volatility_Percent || 0) - (a.Volatility_Percent || 0);
    }).slice(0, 100);
    
    // Render GBM Cards
    renderGBMCards(document.getElementById('volatility-cards-container'), volSorted);

    // Alertas Críticas (TSLA)
    updateTslaMonitor();
    if (volSorted.length === 0) {
        volatilityTableBody.innerHTML = `<tr class="empty-row"><td colspan="7">No hay datos que mostrar.</td></tr>`;
    } else {
        volSorted.forEach(row => {
            const tr = document.createElement("tr");
            tr.onclick = () => selectTicker(row, tr);
            
            const badgeClass = getBadgeClass(row.Viabilidad);
            const vol = row.Volatility_Percent ? `${row.Volatility_Percent.toFixed(2)}%` : '0%';
            
            const levWarning = row.Is_Leveraged ? '<span class="badge evitar" style="font-size:9px;margin-left:4px;">APALANCADO</span>' : '';
            tr.innerHTML = `
                <td><strong>${row.Ticker}${levWarning}</strong></td>
                <td>$${(row.Price || 0).toFixed(2)} <br><small style="color:var(--text-secondary)">$${row.Price_MXN?.toFixed(2) || 'N/A'} MXN</small></td>
                <td style="color: var(--warning-color); font-weight: bold;">${vol}</td>
                <td><span class="badge ${badgeClass}">${row.Viabilidad}</span></td>
                <td>$${row.ATR_MXN?.toFixed(2) || '0'} MXN</td>
                <td>${row.RSI}</td>
                <td>
                    ${row.AI_Confidence_Available === true && hasNumericValue(row.AI_Confidence) ? `<span style="font-size:10px;color:var(--accent-color)">[Histórico:${Number(row.AI_Confidence).toFixed(0)}% · n=${row.AI_Sample_Size || 0}]</span> ` : '<span style="font-size:10px;color:var(--text-secondary)">[Histórico: N/D]</span> '}
                    <span style="max-width: 150px; overflow: hidden; text-overflow: ellipsis; display:inline-block; vertical-align:middle;">${row.Nota || ''}</span>
                </td>
            `;
            volatilityTableBody.appendChild(tr);
        });
    }

    // Gems Table (Breakout Hunters)
    gemsTableBody.innerHTML = "";
    console.log("Total de resultados para filtrar gemas:", allResults.length);
    // Filter for gems: Vol_Ratio > 1.1, MACD bullish, Cap < 100B, AND RSI between 30 and 65 (Not overbought)
    // NOTE: Leveraged ETFs (SOXS, SOXL, TQQQ, etc.) are EXCLUDED because their
    // structural decay makes technical analysis unreliable for long positions.
    const gems = [...allResults].filter(r => {
        if (r.Is_Leveraged) return false; // NUNCA recomendar apalancados como gemas
        const volRatio = r.Vol_Ratio || 0;
        const macdSignal = r.MACD_Signal || r.MACD; // Fallback si no está en caché
        const macdHist = r.MACD_Hist || 0;
        const marketCap = r.Market_Cap || 0;
        
        const isGem = (volRatio >= 1.1) && 
               (r.MACD > macdSignal || macdHist > 0 || r.MACD > 0) &&
               (r.RSI >= 30 && r.RSI < 68) &&
               (marketCap < 200000000000);
               
        return isGem;
    }).sort((a,b) => (b.Vol_Ratio || 0) - (a.Vol_Ratio || 0)).slice(0, 50);
    
    console.log("Gemas encontradas:", gems.length);
    renderGBMCards(document.getElementById('gems-cards-container'), gems);
    
    if (gems.length === 0) {
        gemsTableBody.innerHTML = `<tr class="empty-row"><td colspan="7">No se encontraron gemas en esta búsqueda.</td></tr>`;
    } else {
        gems.forEach(row => {
            const tr = document.createElement("tr");
            tr.onclick = () => selectTicker(row, tr);
            
            const capStr = (row.Market_Cap / 1000000000).toFixed(1) + 'B';
            
            let potClass = "neutro";
            if (row.Vol_Ratio > 2.0) potClass = "alta";
            else if (row.Vol_Ratio > 1.5) potClass = "moderado";
            
            const levWarning = row.Is_Leveraged ? '<span class="badge evitar" style="font-size:9px;margin-left:4px;">APALANCADO</span>' : '';
            tr.innerHTML = `
                <td><strong>${row.Ticker}${levWarning}</strong></td>
                <td>$${(row.Price || 0).toFixed(2)} <br><small style="color:var(--text-secondary)">$${row.Price_MXN?.toFixed(2) || 'N/A'} MXN</small></td>
                <td>$${capStr}</td>
                <td style="color: var(--accent-color); font-weight: bold;">${row.Vol_Ratio || 0}x</td>
                <td>${(row.MACD || 0).toFixed(2)}</td>
                <td>${row.RSI || 'N/A'}</td>
                <td><span class="badge ${potClass}">Breakout Setup</span></td>
            `;
            gemsTableBody.appendChild(tr);
        });
    }
}

function selectTicker(row, trElement) {
    // Highlight row
    document.querySelectorAll(".data-table tbody tr").forEach(tr => tr.classList.remove("selected"));
    if (trElement && trElement.classList) trElement.classList.add("selected");
    
    selectedTickerData = row;
    
    // Update Details Panel
    const badgeClass = getBadgeClass(row.Viabilidad);
    
    const dataStatus = quoteStatus(row);
    const fundamentalsAvailable = row.Fundamentals_Available === true;
    let detailsHTML = `
        <div class="detail-section">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                <h3 style="margin:0; border:none; font-size:18px; color:white;">${row.Ticker}</h3>
                <span class="badge ${badgeClass}">${row.Viabilidad}</span>
            </div>
            ${row.Is_Leveraged ? '<div style="background:rgba(239,68,68,0.15);border:1px solid rgba(239,68,68,0.4);border-radius:8px;padding:8px 12px;margin-bottom:10px;font-size:12px;color:#ef4444;"><strong>ADVERTENCIA:</strong> ETF apalancado. El analisis tecnico clasico NO es aplicable. Estos instrumentos tienen decaimiento estructural por diseno y NO son para hold.</div>' : ''}
            <div class="detail-grid">
                <div class="detail-item"><span class="label">Precio USD</span><span class="val">$${(row.Price || 0).toFixed(2)}</span></div>
                <div class="detail-item"><span class="label">Precio MXN</span><span class="val" style="color:var(--success-color)">$${row.Price_MXN?.toFixed(2) || 'N/A'}</span></div>
                <div class="detail-item"><span class="label">Score Heurístico</span><span class="val" style="color:var(--primary-color)">${row.Score || 0}/100</span></div>
                <div class="detail-item"><span class="label">Score ML</span><span class="val" style="color:var(--accent-color); font-weight:bold;">${row.ML_Source === 'validated_ml_model' && hasNumericValue(row.ML_Score) ? `${Number(row.ML_Score).toFixed(1)}/100 <small style="font-size:10px;opacity:0.8;">(${escapeHtml(row.ML_Confidence || 'ML')})</small>` : `N/D <small style="font-size:10px;opacity:0.8;">(solo heurística${row.ML_Degraded_Reason ? ': '+escapeHtml(row.ML_Degraded_Reason) : ''})</small>`}</span></div>
            </div>
        </div>

        <div class="detail-section data-contract ${dataStatus.cssClass}">
            <h3>Calidad y frescura</h3>
            <p><strong>${dataStatus.label}</strong></p>
            <p>${escapeHtml(dataStatus.detail)}</p>
            ${row.Signal_Eligible === false || row.signal_eligible === false ? '<p class="signal-blocked">SIN SEÑAL: datos vencidos o calidad insuficiente.</p>' : ''}
        </div>
        
        <div class="detail-section">
            <h3>Desglose de Score</h3>
            <div class="detail-grid">
                <div class="detail-item"><span class="label">Técnico</span><span class="val">${hasNumericValue(row.Score_Tech) ? `${row.Score_Tech}/40` : 'N/D'}</span></div>
                <div class="detail-item"><span class="label">Fundamental</span><span class="val">${fundamentalsAvailable && hasNumericValue(row.Score_Fund) ? `${row.Score_Fund}/40` : 'N/D'}</span></div>
                <div class="detail-item"><span class="label">Liquidez</span><span class="val">${hasNumericValue(row.Score_Liq) ? `${row.Score_Liq}/20` : 'N/D'}</span></div>
            </div>
        </div>

        <div class="detail-section">
            <h3>Indicadores Técnicos</h3>
            <div class="detail-grid">
                <div class="detail-item"><span class="label">RSI</span><span class="val">${hasNumericValue(row.RSI) ? row.RSI : 'N/D'}</span></div>
                <div class="detail-item"><span class="label">MACD / señal / hist.</span><span class="val">${hasNumericValue(row.MACD) && hasNumericValue(row.MACD_Signal) && hasNumericValue(row.MACD_Hist) ? `${Number(row.MACD).toFixed(2)} / ${Number(row.MACD_Signal).toFixed(2)} / ${Number(row.MACD_Hist).toFixed(2)}` : 'N/D'}</span></div>
                <div class="detail-item"><span class="label">MA100</span><span class="val">${hasNumericValue(row.MA100) ? '$'+row.MA100 : 'N/D'}</span></div>
                <div class="detail-item"><span class="label">MA200</span><span class="val">${hasNumericValue(row.MA200) ? '$'+row.MA200 : 'N/D'}</span></div>
            </div>
        </div>

        <div class="detail-section">
            <h3>Motor heurístico ${escapeHtml(row.Heuristic_Version || 'sin versión')}</h3>
            <p><strong>Estado:</strong> ${escapeHtml(row.Signal_State || 'SIN SEÑAL')}</p>
            <p><strong>Horizontes:</strong> ${Object.entries(row.Horizon_Scores || {}).map(([name, item]) => `${escapeHtml(name)} ${escapeHtml(item.sessions)}: ${escapeHtml(item.state)} (${Number(item.score).toFixed(2)})`).join(' · ') || 'N/D'}</p>
            <p><strong>Contribuciones:</strong> ${Object.entries(row.Score_Contributions || {}).map(([name, value]) => `${escapeHtml(name)} ${Number(value) >= 0 ? '+' : ''}${Number(value).toFixed(2)}`).join(' · ') || 'N/D'}</p>
            <p><strong>Datos faltantes:</strong> ${row.Heuristic_Version ? ((row.Missing_Indicators || []).map(escapeHtml).join(', ') || 'ninguno') : 'no evaluado (resultado heredado)'}</p>
            ${(row.Signal_Restrictions || []).length ? `<p class="signal-blocked"><strong>Restricciones:</strong> ${row.Signal_Restrictions.map(escapeHtml).join(' · ')}</p>` : ''}
        </div>

        ${row.Fusion_Explanation ? `
        <div class="detail-section" style="border:1px solid var(--primary-color);border-radius:8px;padding:10px;">
            <h3>Veredicto fusionado ${escapeHtml(row.Fusion_Version || '')}</h3>
            <p><strong>A favor:</strong> ${(row.Fusion_Explanation.factors_for || []).map(escapeHtml).join(' · ')}</p>
            <p><strong>En contra:</strong> ${(row.Fusion_Explanation.factors_against || []).map(escapeHtml).join(' · ')}</p>
            <p><strong>Invalidación:</strong> ${(row.Fusion_Explanation.invalidation_triggers || []).map(escapeHtml).join(' · ')}</p>
            ${row.Risk_Plan ? `<p><strong>Riesgo:</strong> ${row.Risk_Plan.position_size_shares} acciones · stop $${Number(row.Risk_Plan.stop_price).toFixed(2)} · pérdida máxima $${Number(row.Risk_Plan.maximum_loss).toFixed(2)} · horizonte ${escapeHtml(row.Risk_Plan.horizon)}</p>` : ''}
        </div>` : ''}

        <div class="detail-section signal-transparency" aria-label="Transparencia de la señal">
            <h3>Qué sabe el sistema y qué no</h3>
            <p><strong>Horizonte:</strong> ${escapeHtml(row.Risk_Plan?.horizon || 'swing 5-20 sesiones')} · <strong>Frescura:</strong> ${escapeHtml(row.Quote?.freshness_seconds ?? 'N/D')} s · <strong>Proveedor:</strong> ${escapeHtml(row.Quote?.provider || 'N/D')}</p>
            <p><strong>Probabilidad ML calibrada:</strong> ${hasNumericValue(row.Calibrated_Probability) ? `${(Number(row.Calibrated_Probability) * 100).toFixed(1)}%` : 'N/D — modelo no aprobado o sin calibración'}</p>
            <p><strong>Heurística:</strong> ${hasNumericValue(row.Score) ? Number(row.Score).toFixed(2) : 'N/D'} · <strong>Fourier:</strong> ${row.Spectral_Validated ? escapeHtml(row.Spectral_Score) : 'experimental, no usado en el veredicto'}</p>
            <p><strong>Calidad de datos:</strong> ${hasNumericValue(row.Data_Quality) ? `${(Number(row.Data_Quality) * 100).toFixed(1)}%` : 'N/D'} · <strong>Incertidumbre:</strong> ${row.Data_Quality < .95 ? 'alta' : (hasNumericValue(row.Calibrated_Probability) ? 'cuantificada' : 'no cuantificada')}</p>
            <p><strong>Versiones:</strong> reglas ${escapeHtml(row.Fusion_Version || 'N/D')} · modelo ${escapeHtml(row.Model_Version || 'N/D')}</p>
            <p class="financial-disclaimer">No garantiza resultados ni constituye asesoría financiera.</p>
        </div>
        
        <div class="detail-section">
            <h3>Volatilidad y Fundamentales</h3>
            <div class="detail-grid">
                <div class="detail-item"><span class="label">ATR USD</span><span class="val">${hasNumericValue(row.ATR) ? '$'+Number(row.ATR).toFixed(2) : 'N/D'}</span></div>
                <div class="detail-item"><span class="label">ATR MXN</span><span class="val">${hasNumericValue(row.ATR_MXN) ? '$'+Number(row.ATR_MXN).toFixed(2) : 'N/D'}</span></div>
                <div class="detail-item"><span class="label">Vol %</span><span class="val">${hasNumericValue(row.Volatility_Percent) ? Number(row.Volatility_Percent).toFixed(2)+'%' : 'N/D'}</span></div>
                <div class="detail-item"><span class="label">Beta</span><span class="val">${fundamentalsAvailable && hasNumericValue(row.Beta) ? row.Beta : 'N/D'}</span></div>
            </div>
        </div>
        
        <div class="detail-section">
            <h3>Notas</h3>
            <p style="color: var(--warning-color); font-size:13px;">${row.Nota || 'Sin notas'}</p>
        </div>
        
        ${row.ML_Breakdown && Object.keys(row.ML_Breakdown).length > 0 ? `
        <div class="detail-section" style="border: 1px solid var(--accent-color); padding: 10px; border-radius: 8px;">
            <h3 style="color: var(--accent-color); margin-top: 0;"><i class="fa-solid fa-brain"></i> Análisis ML Predictivo</h3>
            <div class="detail-grid">
                ${Object.entries(row.ML_Breakdown).map(([k, v]) => `
                    <div class="detail-item">
                        <span class="label">${k}</span>
                        <span class="val" style="color:${v > 0 ? 'var(--success-color)' : 'var(--danger-color)'}">${v > 0 ? '+' : ''}${v}</span>
                    </div>
                `).join('')}
            </div>
            <p style="font-size: 11px; color: var(--text-secondary); margin-top: 8px; margin-bottom: 0;">* Top features de impacto en la predicción actual (Modelo Gradient Boosting).</p>
        </div>
        ` : ''}
    `;
    
    if (detailsContent) detailsContent.innerHTML = detailsHTML;
    
    // Configurar Confianza IA
    const aiConfContent = document.getElementById("ai-confidence-content");
    const feedbackButtons = [
        document.getElementById("btn-feedback-good"),
        document.getElementById("btn-feedback-bad")
    ];
    if (aiConfContent) {
        if (row.AI_Confidence_Available === true && hasNumericValue(row.AI_Confidence)) {
            let color = 'var(--text-secondary)';
            if (row.AI_Confidence >= 70) color = 'var(--success-color)';
            else if (row.AI_Confidence <= 30) color = 'var(--danger-color)';
            
            let notesHtml = row.AI_Notes && row.AI_Notes.length > 0 ? 
                `<ul style="margin: 5px 0 0 15px; padding: 0; font-size: 12px; color: var(--text-secondary);">
                    ${row.AI_Notes.map(n => `<li>${n}</li>`).join('')}
                </ul>` : '';
                
            aiConfContent.innerHTML = `
                <div style="display:flex; align-items:center; justify-content:space-between;">
                    <span style="font-size: 14px; font-weight: 500;">Score Histórico:</span>
                    <span style="font-size: 18px; font-weight: bold; color: ${color};">${row.AI_Confidence.toFixed(1)}%</span>
                </div>
                ${notesHtml}
            `;
            
        } else {
            aiConfContent.innerHTML = `<p class="placeholder-text">Datos de IA no disponibles aún.</p>`;
        }
        const feedbackAvailable = Boolean(row.Prediction_IDs?.['5']);
        const feedbackControls = document.getElementById('feedback-controls');
        if (feedbackControls) feedbackControls.style.display = feedbackAvailable ? 'block' : 'none';
        feedbackButtons.forEach(button => {
            if (!button) return;
            button.style.display = feedbackAvailable ? "block" : "none";
            button.disabled = false;
        });
    }
    
    // Calculate Risk
    calculateRisk(row);
}

async function calculateRisk(row) {
    try {
        const capital = document.getElementById("risk-capital").value;
        const riskPct = document.getElementById("risk-pct").value;
        const atrMult = document.getElementById("risk-atr").value;
        
        const res = await fetch(`${API_URL}/risk/calculate`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                capital: capital,
                price: row.Price,
                atr: row.ATR || 0,
                risk_pct: riskPct,
                atr_multiplier: atrMult
            })
        });
        
        const data = await res.json();
        
        if (data.error) {
            riskOutput.innerHTML = `<p style="color:var(--danger-color)"><i data-lucide="alert-triangle"></i> ${data.error}</p>`;
        } else {
            const levRiskWarn = row.Is_Leveraged ? '<div style="background:rgba(239,68,68,0.15);border:1px solid rgba(239,68,68,0.4);border-radius:8px;padding:8px 12px;margin-bottom:10px;font-size:12px;color:#ef4444;"><strong>NO RECOMENDADO:</strong> Los calculos de riesgo no son confiables en ETFs apalancados. Su volatilidad multiplicada y decaimiento diario invalidan los metodos tradicionales.</div>' : '';
            riskOutput.innerHTML = levRiskWarn + `
                <div style="margin-bottom:10px; font-weight:600; color:white;">Plan para ${row.Ticker}</div>
                <div class="risk-calc-grid">
                    <div class="risk-stat"><span>Acciones</span><span>${data.num_acciones}</span></div>
                    <div class="risk-stat"><span>Inversión</span><span>$${data.capital_requerido}</span></div>
                    <div class="risk-stat stop"><span>Stop-Loss</span><span>$${data.stop_loss}</span></div>
                    <div class="risk-stat target"><span>Target (2:1)</span><span>$${data.precio_objetivo}</span></div>
                    <div class="risk-stat"><span>Riesgo Máx</span><span>$${data.riesgo_maximo}</span></div>
                    <div class="risk-stat target"><span>Beneficio Pot.</span><span>+$${data.beneficio_potencial}</span></div>
                </div>
            `;
        }
        
    } catch (e) {
        console.error("Error calculating risk", e);
    }
}

function updateTslaMonitor() {
    if (!tslaMonitor || !tslaContent) return;
    
    const tslaData = allResults.find(r => r.Ticker === "TSLA");
    if (!tslaData) {
        tslaMonitor.style.display = "none";
        return;
    }
    
    tslaMonitor.style.display = "block";
    const rsi = tslaData.RSI;
    let badgeClass = "hold";
    let actionText = "MANTENER";
    
    if (rsi < 35) {
        badgeClass = "buy"; actionText = "🟢 COMPRA / ENTRADA";
    } else if (rsi > 65) {
        badgeClass = "sell"; actionText = "🛑 VENTA / SALIDA";
    }
    
    const reasons = [];
    if (rsi < 35) reasons.push(`<li><i data-lucide="check"></i> RSI en sobreventa (${rsi})</li>`);
    if (rsi > 65) reasons.push(`<li><i data-lucide="alert-triangle"></i> RSI en sobrecompra (${rsi})</li>`);
    if (String(tslaData.Viabilidad || "").includes("EXCELENTE")) reasons.push(`<li><i class="fa-solid fa-star"></i> Viabilidad Excelente detectada</li>`);
    
    tslaContent.innerHTML = `
        <div class="tsla-price">$${tslaData.Price.toFixed(2)}</div>
        <div class="tsla-badge ${badgeClass}">${actionText}</div>
        <ul class="tsla-reasons">
            ${reasons.length > 0 ? reasons.join('') : '<li><i class="fa-solid fa-circle-notch"></i> Tendencia estable. Sin señales de entrada/salida.</li>'}
        </ul>
        <div style="font-size: 11px; color: var(--text-secondary); margin-top: 10px;">
            Basado en RSI y Viabilidad Técnica Pro.
        </div>
    `;
}

/* ── Global Theme Toggle (v2.7.7) ── */
function toggleTheme() {
    const html = document.documentElement;
    const isDark = html.classList.contains('dark') || html.getAttribute('data-theme') === 'dark';
    const next = isDark ? 'light' : 'dark';
    
    if (next === 'dark') {
        html.classList.add('dark');
        html.classList.remove('light');
        html.setAttribute('data-theme', 'dark');
    } else {
        html.classList.add('light');
        html.classList.remove('dark');
        html.setAttribute('data-theme', 'light');
    }
    
    try { localStorage.setItem('theme', next); } catch (e) {}
    updateThemeIcon(next);
    
    if (window.liquidGL && typeof window.liquidGL.syncWith === 'function') {
        requestAnimationFrame(() => { try { window.liquidGL.syncWith(); } catch(e){} });
    }
}

function updateThemeIcon(theme) {
    const btn = document.getElementById('theme-btn');
    if (btn) {
        btn.innerHTML = theme === 'dark' ? '<i data-lucide="sun"></i>' : '<i data-lucide="moon"></i>';
        btn.setAttribute('title', theme === 'dark' ? 'Cambiar a Modo Claro' : 'Cambiar a Modo Oscuro');
        if (window.lucide && typeof lucide.createIcons === 'function') {
            try { lucide.createIcons(); } catch(e) {}
        }
    }
}

(function() {
    const savedTheme = (function() {
        try { return localStorage.getItem('theme') || 'dark'; } catch(e) { return 'dark'; }
    })();
    document.documentElement.classList.remove('light', 'dark');
    document.documentElement.classList.add(savedTheme);
    document.documentElement.setAttribute('data-theme', savedTheme);
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => updateThemeIcon(savedTheme));
    } else {
        updateThemeIcon(savedTheme);
    }
})();
