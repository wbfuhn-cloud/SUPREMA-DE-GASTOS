
// Auto-initialize Lucide Icons on DOM changes (v2.7.1: guard document.body puede ser null si el script carga en <head>)
if (typeof MutationObserver !== 'undefined' && document.body) {
    const observer = new MutationObserver((mutations) => {
        let shouldUpdate = false;
        for (let mutation of mutations) {
            if (mutation.addedNodes.length) {
                shouldUpdate = true;
                break;
            }
        }
        if (shouldUpdate && window.lucide) {
            try { lucide.createIcons(); } catch (e) { /* iconos opcionales */ }
        }
    });
    try { observer.observe(document.body, { childList: true, subtree: true }); } catch (e) { /* noop */ }
}

const API_URL = "/api";

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

const tabBtns = document.querySelectorAll(".tab-btn");
const tabContents = document.querySelectorAll(".tab-content");

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

// Initialization
document.addEventListener("DOMContentLoaded", async () => {
    // 1. Actualizar estadísticas iniciales
    updateCacheStats();
    
    // 2. Traer inmediatamente los resultados del servidor
    await fetchResults();

    // 3. Cargar estado de escaneo
    await checkScanStatus();
    
    // 4. Si el auto-scan está activo en la UI pero el servidor está libre y sin datos, sugerir inicio
    if (autoScanChk && autoScanChk.checked && !isScanning && allResults.length === 0) {
        console.log("Auto-Scan activo y sin datos: Iniciando escaneo inicial...");
        startScan();
    }
    
    // 4. Cargar portafolio desde la API (sincronizado con el bot)
    try {
        const res = await fetch(`${API_URL}/portfolio/config`);
        const data = await res.json();
        if (data.tickers && data.tickers.length > 0 && document.getElementById("portfolio-input")) {
            document.getElementById("portfolio-input").value = data.tickers.join(', ');
        } else {
            // Fallback a localStorage si la API está vacía
            const savedPortfolio = localStorage.getItem('savedPortfolio');
            if (savedPortfolio && document.getElementById("portfolio-input")) {
                document.getElementById("portfolio-input").value = savedPortfolio;
            }
        }
    } catch (e) {
        console.error("Error cargando portafolio:", e);
    }
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

const btnRefreshPrices = document.getElementById("btn-refresh-prices");
const pricesTbody = document.getElementById("prices-tbody");

if (btnRefreshPrices) {
    btnRefreshPrices.addEventListener("click", loadPricesHistory);
}

// Cargar datos al cambiar de pestaña
tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
        const tabId = btn.dataset.tab;
        if (tabId === 'portfolio-tab') analyzePortfolio();
        if (tabId === 'prices-tab') loadPricesHistory();
        if (tabId === 'ai-tab') { loadLearnerStats(); loadLearnerHistory(); }
    });
});

const btnRefreshAi = document.getElementById("btn-refresh-ai");
if (btnRefreshAi) {
    btnRefreshAi.addEventListener("click", () => {
        loadLearnerStats();
        loadLearnerHistory();
    });
}

const btnFeedbackBad = document.getElementById("btn-feedback-bad");
if (btnFeedbackBad) {
    btnFeedbackBad.addEventListener("click", async () => {
        if (!selectedTickerData) return;
        const ticker = selectedTickerData.Ticker;
        if (!confirm(`¿Estás seguro de reportar la recomendación de ${ticker} como mala?`)) return;
        
        try {
            await fetch(`${API_URL}/learner/feedback`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ticker: ticker, feedback: 'bad' })
            });
            alert(`Gracias por el feedback. Se penalizarán los indicadores de ${ticker}.`);
            btnFeedbackBad.disabled = true;
            btnFeedbackBad.innerHTML = '<i data-lucide="check"></i> Reportado';
            if (document.getElementById('ai-tab').classList.contains('active')) {
                loadLearnerStats();
            }
        } catch (e) {
            console.error("Error enviando feedback", e);
        }
    });
}

async function loadPricesHistory() {
    if (!pricesTbody) return;
    pricesTbody.innerHTML = `<tr><td colspan="7"><i data-lucide="loader" class="lucide-spin"></i> Cargando historial...</td></tr>`;
    
    try {
        const res = await fetch(`${API_URL}/prices/history`);
        const data = await res.json();
        
        if (data.status === 'ok') {
            pricesTbody.innerHTML = '';
            if (data.prices.length === 0) {
                pricesTbody.innerHTML = `<tr class="empty-row"><td colspan="7">No hay hallazgos registrados aún.</td></tr>`;
                return;
            }
            
            data.prices.forEach(row => {
                const tr = document.createElement('tr');
                const fecha = row.fecha.replace('T', ' ').substring(0, 16);
                const desc = row.descuento_pct ? `<span class="badge alta">-${row.descuento_pct}%</span>` : '—';
                
                tr.innerHTML = `
                    <td>${fecha}</td>
                    <td><span class="badge neutro">${row.tienda}</span></td>
                    <td>${row.producto_buscado}</td>
                    <td style="font-size:0.85em">${row.nombre}</td>
                    <td style="font-weight:bold; color:var(--success-color)">$${row.precio_actual.toLocaleString()}</td>
                    <td>${desc}</td>
                    <td><a href="${row.url}" target="_blank" class="btn sm-btn primary-btn"><i class="fa-solid fa-external-link"></i> Ver</a></td>
                `;
                pricesTbody.appendChild(tr);
            });
        }
    } catch (e) {
        console.error("Error loading prices", e);
        pricesTbody.innerHTML = `<tr><td colspan="7" style="color:var(--danger-color)">Error al cargar datos</td></tr>`;
    }
}

async function loadLearnerStats() {
    try {
        const res = await fetch(`${API_URL}/learner/stats`);
        const data = await res.json();
        if (data.status === 'ok') {
            document.getElementById('ai-accuracy').textContent = `${data.stats.accuracy_pct}%`;
            
            const avg = data.stats.avg_change_1d;
            const avgEl = document.getElementById('ai-avg-change');
            avgEl.textContent = `${avg > 0 ? '+' : ''}${avg}%`;
            avgEl.style.color = avg > 0 ? 'var(--success-color)' : (avg < 0 ? 'var(--danger-color)' : 'white');
            
            document.getElementById('ai-verified').textContent = data.stats.verified;
            document.getElementById('ai-adjustments').textContent = data.stats.total_adjustments;
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
        }
    } catch (e) {
        console.error("Error loading learner stats", e);
    }
}

async function loadLearnerHistory() {
    const tbody = document.getElementById('ai-history-tbody');
    if (!tbody) return;
    
    tbody.innerHTML = `<tr><td colspan="6"><i data-lucide="loader" class="lucide-spin"></i> Cargando historial...</td></tr>`;
    try {
        const res = await fetch(`${API_URL}/learner/history`);
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
                if (outcome === 'good_strong' || outcome === 'good_mild') {
                    evalBadge = "alta"; evalText = "🟢 Acertó";
                } else if (outcome === 'bad_severe' || outcome === 'bad_mild') {
                    evalBadge = "evitar"; evalText = "🔴 Falló";
                }
                
                const change = row.change_pct_1d !== null ? `${row.change_pct_1d > 0 ? '+' : ''}${row.change_pct_1d.toFixed(2)}%` : '--';
                const changeColor = row.change_pct_1d > 0 ? 'var(--success-color)' : (row.change_pct_1d < 0 ? 'var(--danger-color)' : 'white');
                
                tr.innerHTML = `
                    <td>${row.scan_date}</td>
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

filterViability.addEventListener("change", renderTables);
searchTicker.addEventListener("input", renderTables);

tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
        tabBtns.forEach(b => b.classList.remove("active"));
        tabContents.forEach(c => c.classList.remove("active"));
        btn.classList.add("active");
        document.getElementById(btn.dataset.tab).classList.add("active");
    });
});

document.querySelectorAll(".risk-inputs input").forEach(input => {
    input.addEventListener("input", () => {
        if (selectedTickerData) calculateRisk(selectedTickerData);
    });
});

autoScanChk.addEventListener("change", (e) => {
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
        cacheStats.innerHTML = `<i data-lucide="zap"></i> Caché: ${dCache.total_tickers} stocks | ${dCache.total_size_mb.toFixed(1)} MB | Listas: ${data.ticker_cache.cached_sources}`;
    } catch (e) {
        console.error("Error fetching cache stats", e);
    }
}

async function clearCache(target) {
    if(!confirm(`¿Estás seguro de que quieres limpiar la caché de ${target}?`)) return;
    try {
        await fetch(`${API_URL}/cache/clear`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ target })
        });
        updateCacheStats();
    } catch (e) {
        console.error("Error clearing cache", e);
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
        alert("Por favor completa todos los campos correctamente.");
        return;
    }
    
    btnAddPortfolio.disabled = true;
    try {
        await fetch(`${API_URL}/portfolio/update`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ticker, qty, price })
        });
        portTicker.value = "";
        portPrice.value = "";
        analyzePortfolio();
    } catch (e) {
        console.error("Error adding to portfolio", e);
    }
    btnAddPortfolio.disabled = false;
}

async function analyzePortfolio() {
    portfolioTbody.innerHTML = `<tr><td colspan="6"><i data-lucide="loader" class="lucide-spin"></i> Analizando Cartera...</td></tr>`;
    
    try {
        const res = await fetch(`${API_URL}/portfolio/analyze`, { method: "POST" });
        const data = await res.json();
        
        if (data.status === 'ok') {
            portfolioTbody.innerHTML = '';
            if (data.results.length === 0) {
                portfolioTbody.innerHTML = `<tr class="empty-row"><td colspan="6">Agrega tus posiciones arriba para que el asesor las monitoree.</td></tr>`;
                return;
            }
            
            data.results.forEach(row => {
                const tr = document.createElement('tr');
                if (row.error) {
                    tr.innerHTML = `
                        <td><strong>${row.ticker}</strong></td>
                        <td colspan="4" style="color:var(--danger-color)">${row.error}</td>
                        <td><button onclick="removePortfolioItem('${row.ticker}')" class="btn sm-btn danger-btn"><i class="fa-solid fa-trash"></i></button></td>
                    `;
                } else {
                    let badgeClass = "neutro";
                    if(row.verdict.includes("COMPRA") || row.verdict.includes("AUMENTA")) badgeClass = "alta";
                    else if(row.verdict.includes("MANTEN") || row.verdict.includes("MEDIA")) badgeClass = "moderado";
                    else if(row.verdict.includes("VENTA") || row.verdict.includes("EVITAR") || row.verdict.includes("REDUCIR")) badgeClass = "evitar";
                    
                    const plColor = row.pl_pct >= 0 ? "var(--success-color)" : "var(--danger-color)";
                    const plSign = row.pl_pct >= 0 ? "+" : "";
                    
                    const levFlag = row.is_leveraged ? ' <span class="badge evitar" style="font-size:9px">APALANCADO</span>' : '';
                    tr.innerHTML = `
                        <td><strong>${row.ticker}${levFlag}</strong></td>
                        <td>${row.qty} @ $${row.entry_price}</td>
                        <td>$${row.price} <br><small style="color:var(--text-secondary)">$${row.price_mxn} MXN</small></td>
                        <td><span class="badge ${badgeClass}">${row.verdict}</span></td>
                        <td style="color: ${plColor}; font-weight: bold;">
                            ${plSign}${row.pl_pct}% <br>
                            <small style="opacity:0.8">${plSign}$${row.pl_val} USD</small>
                            ${row.pl_mxn ? `<br><small style="opacity:0.7">${plSign}$${row.pl_mxn} MXN</small>` : ''}
                        </td>
                        <td>
                            <button onclick="removePortfolioItem('${row.ticker}')" class="btn sm-btn danger-btn" title="Eliminar"><i class="fa-solid fa-trash"></i></button>
                        </td>
                    `;
                }
                portfolioTbody.appendChild(tr);
            });
        }
    } catch (e) {
        console.error("Error analyzing portfolio", e);
        portfolioTbody.innerHTML = `<tr><td colspan="6" style="color:var(--danger-color)">Error de conexión</td></tr>`;
    }
}

async function removePortfolioItem(ticker) {
    if (!confirm(`¿Eliminar ${ticker} del portafolio?`)) return;
    try {
        // En server.py creamos una lógica para borrar o actualizar
        await fetch(`${API_URL}/portfolio/config`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ 
                action: 'remove', 
                ticker: ticker 
            })
        });
        analyzePortfolio();
    } catch (e) {}
}

function startStatusPolling() {
    if (statusInterval) clearInterval(statusInterval);
    statusInterval = setInterval(checkScanStatus, 1000);
}

async function checkScanStatus() {
    try {
        const res = await fetch(`${API_URL}/scan/status`);
        const data = await res.json();
        
        progressBar.style.width = `${data.progress * 100}%`;
        progressText.textContent = data.message;
        
        if (!data.is_scanning && isScanning) {
            // Scan just finished
            isScanning = false;
            clearInterval(statusInterval);
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
    try {
        const res = await fetch(`${API_URL}/scan/results`);
        const data = await res.json();
        
        allResults = data.results || [];
        updateMarketContext(data.market_context);
        renderTables();
    } catch (e) {
        console.error("Error fetching results", e);
    }
}

// UI Rendering
function updateMarketContext(ctx) {
    if (!ctx) return;
    let icon = "globe", colorClass = "neutral";
    if (ctx.regime.includes("ALCISTA")) { icon = "arrow-trend-up"; colorClass = "alcista"; }
    else if (ctx.regime.includes("BAJISTA")) { icon = "arrow-trend-down"; colorClass = "bajista"; }
    
    marketStatus.innerHTML = `
        <span class="status-indicator ${colorClass}">
            <i class="fa-solid fa-${icon}"></i> ${ctx.regime} | VIX: ${ctx.vix} | SPY vs SMA200: ${ctx.spy_vs_sma200}%
        </span>
    `;
}

function getBadgeClass(viability) {
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
        const aiConf = row.AI_Confidence ? `${row.AI_Confidence.toFixed(0)}%` : 'N/A';
        const aiConfClass = (row.AI_Confidence > 75) ? 'alta' : (row.AI_Confidence > 50) ? 'media' : 'baja';

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
                    ${row.AI_Confidence ? `<span style="font-size:10px;color:var(--accent-color)">[IA:${row.AI_Confidence.toFixed(0)}%]</span> ` : ''}
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
    trElement.classList.add("selected");
    
    selectedTickerData = row;
    
    // Update Details Panel
    const badgeClass = getBadgeClass(row.Viabilidad);
    
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
                <div class="detail-item"><span class="label">ML Score (IA)</span><span class="val" style="color:var(--accent-color); font-weight:bold;">${row.ML_Score !== undefined ? row.ML_Score : (row.Score || 0)}/100 <small style="font-size:10px;opacity:0.8;">(${row.ML_Confidence || 'ML'})</small></span></div>
            </div>
        </div>
        
        <div class="detail-section">
            <h3>Desglose de Score</h3>
            <div class="detail-grid">
                <div class="detail-item"><span class="label">Técnico</span><span class="val">${row.Score_Tech || 0}/40</span></div>
                <div class="detail-item"><span class="label">Fundamental</span><span class="val">${row.Score_Fund || 0}/40</span></div>
                <div class="detail-item"><span class="label">Liquidez</span><span class="val">${row.Score_Liq || 0}/20</span></div>
            </div>
        </div>

        <div class="detail-section">
            <h3>Indicadores Técnicos</h3>
            <div class="detail-grid">
                <div class="detail-item"><span class="label">RSI</span><span class="val">${row.RSI || 'N/A'}</span></div>
                <div class="detail-item"><span class="label">MACD</span><span class="val">${(row.MACD || 0).toFixed(2)}</span></div>
                <div class="detail-item"><span class="label">MA100</span><span class="val">$${row.MA100}</span></div>
                <div class="detail-item"><span class="label">MA200</span><span class="val">$${row.MA200}</span></div>
            </div>
        </div>
        
        <div class="detail-section">
            <h3>Volatilidad y Fundamentales</h3>
            <div class="detail-grid">
                <div class="detail-item"><span class="label">ATR USD</span><span class="val">${row.ATR ? '$'+row.ATR.toFixed(2) : 'N/A'}</span></div>
                <div class="detail-item"><span class="label">ATR MXN</span><span class="val">${row.ATR_MXN ? '$'+row.ATR_MXN.toFixed(2) : 'N/A'}</span></div>
                <div class="detail-item"><span class="label">Vol %</span><span class="val">${row.Volatility_Percent ? row.Volatility_Percent.toFixed(2)+'%' : 'N/A'}</span></div>
                <div class="detail-item"><span class="label">Beta</span><span class="val">${row.Beta}</span></div>
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
    const btnFeedback = document.getElementById("btn-feedback-bad");
    if (aiConfContent) {
        if (row.AI_Confidence) {
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
            
            if (btnFeedback) {
                btnFeedback.style.display = "block";
                btnFeedback.disabled = false;
                btnFeedback.innerHTML = '<i data-lucide="thumbs-down"></i> Reportar como mala';
            }
        } else {
            aiConfContent.innerHTML = `<p class="placeholder-text">Datos de IA no disponibles aún.</p>`;
            if (btnFeedback) btnFeedback.style.display = "none";
        }
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
    if (tslaData.Viabilidad.includes("EXCELENTE")) reasons.push(`<li><i class="fa-solid fa-star"></i> Viabilidad Excelente detectada</li>`);
    
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

/* ── Global Theme Toggle ── */
function toggleTheme() {
    const html = document.documentElement;
    const next = html.classList.contains('dark') ? 'light' : 'dark';
    if (next === 'dark') {
        html.classList.add('dark'); html.setAttribute('data-theme', 'dark');
        html.classList.remove('light');
    } else {
        html.classList.add('light'); html.setAttribute('data-theme', 'light');
        html.classList.remove('dark');
    }
    localStorage.setItem('theme', next);
    updateThemeIcon(next);
}

function updateThemeIcon(theme) {
    const btn = document.getElementById('theme-btn');
    if (btn) {
        btn.innerHTML = theme === 'dark' ? '<i data-lucide="sun"></i>' : '<i data-lucide="moon"></i>';
        if(window.lucide) { lucide.createIcons(); }
    }
}

(function() {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    document.documentElement.className = savedTheme;
    updateThemeIcon(savedTheme);
})();
