// State
let currentView = 'home';
let currentSymbol = null;
let activeToast = null;
let sortBy = 'mtm';
let sortAsc = false;
let fbnAccounts = [];

// Status helpers
function setStatus(msg, type = '') {
    const el = document.getElementById('status');
    el.textContent = msg;
    el.className = type;
}

// Toast notifications
function showToast(message, type = 'info', duration = 0) {
    const container = document.getElementById('toast-container');

    // Remove existing loading toast if showing a result
    if (activeToast && type !== 'loading') {
        activeToast.remove();
        activeToast = null;
    }

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    if (type === 'loading') {
        toast.innerHTML = `<span class="spinner"></span>${message}`;
        activeToast = toast;
    } else {
        toast.textContent = message;
        // Auto-remove success/error toasts
        if (duration === 0) duration = type === 'error' ? 5000 : 3000;
        setTimeout(() => {
            toast.classList.add('fade-out');
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }

    container.appendChild(toast);
    return toast;
}

function hideLoadingToast() {
    if (activeToast) {
        activeToast.remove();
        activeToast = null;
    }
}

// API helpers
async function api(endpoint, options = {}) {
    setStatus('Loading...', 'loading');
    try {
        const response = await fetch(`/api${endpoint}`, {
            headers: { 'Content-Type': 'application/json' },
            ...options
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Request failed');
        }
        const data = await response.json();
        setStatus('Ready');
        return data;
    } catch (err) {
        setStatus(err.message, 'error');
        throw err;
    }
}

// Navigation
function showHome() {
    document.querySelectorAll('.view').forEach(v => v.classList.add('hidden'));
    document.getElementById('home-view').classList.remove('hidden');
    document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
    document.querySelector('.nav-link').classList.add('active');
    currentView = 'home';
}

function showIBKR() {
    document.querySelectorAll('.view').forEach(v => v.classList.add('hidden'));
    document.getElementById('ibkr-view').classList.remove('hidden');
    document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
    document.querySelectorAll('.nav-link')[1].classList.add('active');
    currentView = 'ibkr';
    loadPositions();
}

function showFBN() {
    document.querySelectorAll('.view').forEach(v => v.classList.add('hidden'));
    document.getElementById('fbn-view').classList.remove('hidden');
    document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
    document.querySelectorAll('.nav-link')[2].classList.add('active');
    currentView = 'fbn';
    loadFBNMonthlyStats();
}

// Format helpers
function fmt(val, decimals = 2) {
    if (val === null || val === undefined || val === '') return '';
    const num = parseFloat(val);
    if (isNaN(num)) return '';
    return num.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function fmtInt(val) {
    if (val === null || val === undefined || val === '' || val === 0) return '';
    return Math.round(val).toLocaleString('en-US');
}

function pnlClass(val) {
    if (val > 0) return 'positive';
    if (val < 0) return 'negative';
    return '';
}

// IBKR: Load Positions
async function loadPositions() {
    try {
        const data = await api(`/ibkr/positions?sort_by=${sortBy}&ascending=${sortAsc}`);
        renderPositions(data);
    } catch (err) {
        document.getElementById('ibkr-content').innerHTML = `<p class="error">${err.message}</p>`;
    }
}

function sortPositions(column) {
    if (sortBy === column) {
        sortAsc = !sortAsc;
    } else {
        sortBy = column;
        sortAsc = column === 'symbol';  // Default ascending for symbol, descending for others
    }
    loadPositions();
}

function sortIndicator(column) {
    if (sortBy !== column) return '';
    return sortAsc ? ' ▲' : ' ▼';
}

function renderPositions(data) {
    const { positions, totals } = data;

    let html = '<div class="table-container"><table>';
    html += `<tr>
        <th class="sortable" onclick="sortPositions('symbol')">Symbol${sortIndicator('symbol')}</th>
        <th>Value</th>
        <th class="sortable" onclick="sortPositions('mtm')">MTM${sortIndicator('mtm')}</th>
        <th>MTM%</th>
        <th>Tgt%</th>
        <th>Unrlzd PnL</th>
        <th class="sortable" onclick="sortPositions('s_qty')">Stock${sortIndicator('s_qty')}</th>
        <th>Call</th>
        <th>Put</th>
        <th>Stock PnL</th>
        <th>Call PnL</th>
        <th>Put PnL</th>
    </tr>`;

    for (const p of positions) {
        html += `<tr>
            <td class="symbol clickable" onclick="showPositionDetail('${p.symbol}')">${p.symbol}</td>
            <td class="num">${fmt(p.value)}</td>
            <td class="num">${fmt(p.mtm)}</td>
            <td class="num">${fmt(p.mtm_pct)}%</td>
            <td class="num">${p.target_pct ? fmt(p.target_pct) + '%' : ''}</td>
            <td class="num ${pnlClass(p.unrlzd_pnl)}">${fmt(p.unrlzd_pnl)}</td>
            <td class="num qty">${fmtInt(p.s_qty)}</td>
            <td class="num qty">${fmtInt(p.c_qty)}</td>
            <td class="num qty">${fmtInt(p.p_qty)}</td>
            <td class="num ${pnlClass(p.s_pnl)}">${fmt(p.s_pnl)}</td>
            <td class="num ${pnlClass(p.c_pnl)}">${fmt(p.c_pnl)}</td>
            <td class="num ${pnlClass(p.p_pnl)}">${fmt(p.p_pnl)}</td>
        </tr>`;
    }

    html += `<tr class="totals">
        <td>TOTAL</td>
        <td class="num">${fmt(totals.value)}</td>
        <td class="num">${fmt(totals.mtm)}</td>
        <td class="num">100%</td>
        <td class="num">${fmt(totals.target_pct)}%</td>
        <td class="num ${pnlClass(totals.unrlzd_pnl)}">${fmt(totals.unrlzd_pnl)}</td>
        <td class="num qty">${fmtInt(totals.s_qty)}</td>
        <td class="num qty">${fmtInt(totals.c_qty)}</td>
        <td class="num qty">${fmtInt(totals.p_qty)}</td>
        <td class="num ${pnlClass(totals.s_pnl)}">${fmt(totals.s_pnl)}</td>
        <td class="num ${pnlClass(totals.c_pnl)}">${fmt(totals.c_pnl)}</td>
        <td class="num ${pnlClass(totals.p_pnl)}">${fmt(totals.p_pnl)}</td>
    </tr>`;

    html += '</table></div>';
    document.getElementById('ibkr-content').innerHTML = html;
}

// IBKR: Position Detail
async function showPositionDetail(symbol) {
    currentSymbol = symbol;
    try {
        const data = await api(`/ibkr/positions/${symbol}`);
        renderPositionDetail(data);
        document.getElementById('position-modal').classList.remove('hidden');
    } catch (err) {
        setStatus(err.message, 'error');
    }
}

function renderPositionDetail(data) {
    const { summary, trades } = data;

    let html = `<div class="summary-box">
        <h3>${summary.symbol}</h3>
        <div class="summary-grid">
            <span class="summary-label">Book Price:</span>
            <span class="summary-value">${fmt(summary.book_price)}</span>
            <span class="summary-label">Stock Qty:</span>
            <span class="summary-value qty">${fmtInt(summary.stock_qty)}</span>
            <span class="summary-label">Call Qty:</span>
            <span class="summary-value qty">${fmtInt(summary.call_qty)}</span>
            <span class="summary-label">Put Qty:</span>
            <span class="summary-value qty">${fmtInt(summary.put_qty)}</span>
            <span class="summary-label">Stock PnL:</span>
            <span class="summary-value ${pnlClass(summary.stock_pnl)}">${fmt(summary.stock_pnl)}</span>
            <span class="summary-label">Call PnL:</span>
            <span class="summary-value ${pnlClass(summary.call_pnl)}">${fmt(summary.call_pnl)}</span>
            <span class="summary-label">Put PnL:</span>
            <span class="summary-value ${pnlClass(summary.put_pnl)}">${fmt(summary.put_pnl)}</span>
        </div>
    </div>`;

    html += '<table>';
    html += `<tr>
        <th>Date</th>
        <th>Desc</th>
        <th>P/C</th>
        <th>Qty</th>
        <th>Price</th>
        <th>Comm</th>
        <th>O/C</th>
        <th>Realized PnL</th>
        <th>Rem Qty</th>
        <th>Credit</th>
        <th>Delta</th>
        <th>Und Price</th>
        <th></th>
    </tr>`;

    for (const t of trades) {
        html += `<tr>
            <td>${t.dateTime}</td>
            <td>${t.description || ''}</td>
            <td>${t.putCall || ''}</td>
            <td class="num qty">${fmtInt(t.quantity)}</td>
            <td class="num">${fmt(t.tradePrice)}</td>
            <td class="num">${fmt(t.ibCommission)}</td>
            <td>${t.openCloseIndicator || ''}</td>
            <td class="num ${pnlClass(t.realized_pnl)}">${t.realized_pnl ? fmt(t.realized_pnl) : ''}</td>
            <td class="num qty">${t.remaining_qty ? fmtInt(t.remaining_qty) : ''}</td>
            <td class="num">${t.credit ? fmt(t.credit) : ''}</td>
            <td class="num">${t.delta ? fmt(t.delta, 4) : ''}</td>
            <td class="num">${t.und_price ? fmt(t.und_price) : ''}</td>
            <td><span class="edit-btn" onclick="openEditModal('${t.tradeID}', ${t.delta || 'null'}, ${t.und_price || 'null'})">[edit]</span></td>
        </tr>`;
    }

    html += '</table>';
    document.getElementById('position-detail-content').innerHTML = html;
}

function closeModal() {
    document.getElementById('position-modal').classList.add('hidden');
}

// IBKR: Edit Trade
function openEditModal(tradeId, delta, undPrice) {
    document.getElementById('edit-trade-id').value = tradeId;
    document.getElementById('edit-delta').value = delta !== null ? delta : '';
    document.getElementById('edit-und-price').value = undPrice !== null ? undPrice : '';
    document.getElementById('edit-modal').classList.remove('hidden');
}

function closeEditModal() {
    document.getElementById('edit-modal').classList.add('hidden');
}

async function submitTradeEdit(event) {
    event.preventDefault();
    const tradeId = document.getElementById('edit-trade-id').value;
    const delta = document.getElementById('edit-delta').value;
    const undPrice = document.getElementById('edit-und-price').value;

    const body = {};
    if (delta !== '') body.delta = parseFloat(delta);
    if (undPrice !== '') body.und_price = parseFloat(undPrice);

    try {
        await api(`/ibkr/trades/${tradeId}`, {
            method: 'PATCH',
            body: JSON.stringify(body)
        });
        setStatus('Trade updated', 'success');
        closeEditModal();
        if (currentSymbol) {
            showPositionDetail(currentSymbol);
        }
    } catch (err) {
        // Error already shown by api()
    }
}

// IBKR: All Trades
async function loadTrades() {
    try {
        const data = await api('/ibkr/trades');
        renderTrades(data);
    } catch (err) {
        document.getElementById('ibkr-content').innerHTML = `<p class="error">${err.message}</p>`;
    }
}

function renderTrades(trades) {
    let html = '<div class="table-container"><table>';
    html += `<tr>
        <th>Date</th>
        <th>Symbol</th>
        <th>Desc</th>
        <th>Qty</th>
        <th>Price</th>
        <th>Comm</th>
        <th>O/C</th>
        <th>PnL</th>
        <th>Rem Qty</th>
    </tr>`;

    for (const t of trades) {
        html += `<tr>
            <td>${t.dateTime || ''}</td>
            <td class="symbol">${t.symbol}</td>
            <td>${t.description || ''}</td>
            <td class="num qty">${fmtInt(t.quantity)}</td>
            <td class="num">${fmt(t.tradePrice)}</td>
            <td class="num">${fmt(t.ibCommission)}</td>
            <td>${t.openCloseIndicator || ''}</td>
            <td class="num ${pnlClass(t.realized_pnl)}">${t.realized_pnl ? fmt(t.realized_pnl) : ''}</td>
            <td class="num qty">${t.remaining_qty ? fmtInt(t.remaining_qty) : ''}</td>
        </tr>`;
    }

    html += '</table></div>';
    document.getElementById('ibkr-content').innerHTML = html;
}

// IBKR: Daily Stats
async function loadDailyStats() {
    try {
        const data = await api('/ibkr/stats/daily');
        renderDailyStats(data);
    } catch (err) {
        document.getElementById('ibkr-content').innerHTML = `<p class="error">${err.message}</p>`;
    }
}

function renderDailyStats(data) {
    const { stats, total } = data;

    let html = '<div class="table-container"><table class="stats-table">';
    html += `<tr><th>Date</th><th>Day</th><th>PnL</th></tr>`;

    for (const s of stats) {
        const pnlStr = s.pnl !== 0 ? fmt(s.pnl) : '-';
        html += `<tr>
            <td>${s.date}</td>
            <td class="day">${s.day}</td>
            <td class="num ${pnlClass(s.pnl)}">${pnlStr}</td>
        </tr>`;
    }

    html += `<tr class="totals">
        <td colspan="2">TOTAL</td>
        <td class="num ${pnlClass(total)}">${fmt(total)}</td>
    </tr>`;

    html += '</table></div>';
    document.getElementById('ibkr-content').innerHTML = html;
}

// IBKR: Weekly Stats
async function loadWeeklyStats() {
    try {
        const data = await api('/ibkr/stats/weekly');
        renderWeeklyStats(data);
    } catch (err) {
        document.getElementById('ibkr-content').innerHTML = `<p class="error">${err.message}</p>`;
    }
}

function renderWeeklyStats(data) {
    const { stats, total } = data;

    let html = '<div class="table-container"><table class="stats-table">';
    html += `<tr><th>Week Ending</th><th>PnL</th></tr>`;

    for (const s of stats) {
        const pnlStr = s.pnl !== 0 ? fmt(s.pnl) : '-';
        html += `<tr>
            <td>${s.week_ending}</td>
            <td class="num ${pnlClass(s.pnl)}">${pnlStr}</td>
        </tr>`;
    }

    html += `<tr class="totals">
        <td>TOTAL</td>
        <td class="num ${pnlClass(total)}">${fmt(total)}</td>
    </tr>`;

    html += '</table></div>';
    document.getElementById('ibkr-content').innerHTML = html;
}

// IBKR: Import
async function importTrades(queryType) {
    const btn = event.target;
    btn.disabled = true;

    showToast(`Importing ${queryType} trades...`, 'loading');

    try {
        const data = await api('/ibkr/import', {
            method: 'POST',
            body: JSON.stringify({ query_type: queryType })
        });
        showToast(data.message, 'success');
        loadPositions();
    } catch (err) {
        showToast(err.message || 'Import failed', 'error');
    } finally {
        btn.disabled = false;
    }
}

// IBKR: Update MTM
async function updateMTM() {
    const btn = event.target;
    btn.disabled = true;

    showToast('Updating market prices...', 'loading');

    try {
        const data = await api('/ibkr/mtm', { method: 'POST' });
        showToast(data.message, 'success');
        loadPositions();
    } catch (err) {
        showToast(err.message || 'MTM update failed', 'error');
    } finally {
        btn.disabled = false;
    }
}

// ============================================
// FBN Functions
// ============================================

// FBN: Load Monthly Stats
async function loadFBNMonthlyStats() {
    try {
        const data = await api('/fbn/stats/monthly');
        renderFBNMonthlyStats(data);
    } catch (err) {
        document.getElementById('fbn-content').innerHTML = `<p class="error">${err.message}</p>`;
    }
}

function renderFBNMonthlyStats(data) {
    const { stats, totals } = data;

    let html = '<div class="table-container"><table class="stats-table">';
    html += `<tr>
        <th>Date</th>
        <th>Deposit</th>
        <th>Asset</th>
        <th>Fee</th>
        <th>PnL</th>
        <th>Pct</th>
    </tr>`;

    for (const s of stats) {
        html += `<tr>
            <td>${s.date}</td>
            <td class="num">${s.deposit !== 0 ? fmt(s.deposit) : '-'}</td>
            <td class="num">${fmt(s.asset)}</td>
            <td class="num">${s.fee !== 0 ? fmt(s.fee) : '-'}</td>
            <td class="num ${pnlClass(s.pnl)}">${fmt(s.pnl)}</td>
            <td class="num ${pnlClass(s.pct)}">${fmt(s.pct)}%</td>
        </tr>`;
    }

    html += `<tr class="totals">
        <td>TOTAL</td>
        <td class="num">${fmt(totals.deposit)}</td>
        <td class="num">${fmt(totals.asset)}</td>
        <td class="num">${fmt(totals.fee)}</td>
        <td class="num ${pnlClass(totals.pnl)}">${fmt(totals.pnl)}</td>
        <td class="num">-</td>
    </tr>`;

    html += '</table></div>';
    document.getElementById('fbn-content').innerHTML = html;
}

// FBN: Load Yearly Stats
async function loadFBNYearlyStats() {
    try {
        const data = await api('/fbn/stats/yearly');
        renderFBNYearlyStats(data);
    } catch (err) {
        document.getElementById('fbn-content').innerHTML = `<p class="error">${err.message}</p>`;
    }
}

function renderFBNYearlyStats(data) {
    const { stats, totals } = data;

    let html = '<div class="table-container"><table class="stats-table">';
    html += `<tr>
        <th>Year</th>
        <th>Deposit</th>
        <th>Asset</th>
        <th>Fee</th>
        <th>PnL</th>
        <th>Pct</th>
    </tr>`;

    for (const s of stats) {
        html += `<tr>
            <td>${s.year}</td>
            <td class="num">${s.deposit !== 0 ? fmt(s.deposit) : '-'}</td>
            <td class="num">${fmt(s.asset)}</td>
            <td class="num">${s.fee !== 0 ? fmt(s.fee) : '-'}</td>
            <td class="num ${pnlClass(s.pnl)}">${fmt(s.pnl)}</td>
            <td class="num ${pnlClass(s.pct)}">${fmt(s.pct)}%</td>
        </tr>`;
    }

    html += `<tr class="totals">
        <td>TOTAL</td>
        <td class="num">${fmt(totals.deposit)}</td>
        <td class="num">${fmt(totals.asset)}</td>
        <td class="num">${fmt(totals.fee)}</td>
        <td class="num ${pnlClass(totals.pnl)}">${fmt(totals.pnl)}</td>
        <td class="num">-</td>
    </tr>`;

    html += '</table></div>';
    document.getElementById('fbn-content').innerHTML = html;
}

// FBN: Load Monthly Matrix
async function loadFBNMonthlyMatrix() {
    try {
        const data = await api('/fbn/matrix/monthly');
        renderFBNMatrix(data, 'date', 'Monthly Assets Matrix');
    } catch (err) {
        document.getElementById('fbn-content').innerHTML = `<p class="error">${err.message}</p>`;
    }
}

// FBN: Load Yearly Matrix
async function loadFBNYearlyMatrix() {
    try {
        const data = await api('/fbn/matrix/yearly');
        renderFBNMatrix(data, 'year', 'Yearly Assets Matrix');
    } catch (err) {
        document.getElementById('fbn-content').innerHTML = `<p class="error">${err.message}</p>`;
    }
}

function renderFBNMatrix(data, rowKey, title) {
    const { accounts, data: rows } = data;

    let html = '<div class="table-container"><table class="matrix-table">';
    html += `<tr><th>${rowKey === 'date' ? 'Date' : 'Year'}</th>`;
    for (const acc of accounts) {
        html += `<th>${acc}</th>`;
    }
    html += '<th class="total-col">Total</th></tr>';

    for (const row of rows) {
        html += `<tr><td>${row[rowKey]}</td>`;
        for (const acc of accounts) {
            const val = row[acc];
            html += `<td class="num">${val !== null ? fmt(val) : '-'}</td>`;
        }
        html += `<td class="num total-col">${fmt(row.total)}</td></tr>`;
    }

    html += '</table></div>';
    document.getElementById('fbn-content').innerHTML = html;
}

// FBN: Entry Modal
async function openFBNEntryModal() {
    // Load accounts if not already loaded
    if (fbnAccounts.length === 0) {
        try {
            fbnAccounts = await api('/fbn/accounts');
        } catch (err) {
            showToast('Failed to load accounts', 'error');
            return;
        }
    }

    // Populate account dropdown
    const select = document.getElementById('fbn-account');
    select.innerHTML = '<option value="">Select account...</option>';
    for (const acc of fbnAccounts) {
        select.innerHTML += `<option value="${acc.name}" data-portfolio="${acc.portfolio}" data-currency="${acc.currency}">${acc.name} (${acc.currency})</option>`;
    }

    // Set default date to last day of previous month
    const today = new Date();
    const firstOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);
    const lastOfPrevMonth = new Date(firstOfMonth - 1);
    document.getElementById('fbn-date').value = lastOfPrevMonth.toISOString().split('T')[0];

    // Reset form
    resetFBNForm();

    document.getElementById('fbn-entry-modal').classList.remove('hidden');
}

function closeFBNEntryModal() {
    document.getElementById('fbn-entry-modal').classList.add('hidden');
}

function resetFBNForm() {
    document.getElementById('fbn-investment').value = 0;
    document.getElementById('fbn-deposit').value = 0;
    document.getElementById('fbn-interest').value = 0;
    document.getElementById('fbn-dividend').value = 0;
    document.getElementById('fbn-distribution').value = 0;
    document.getElementById('fbn-tax').value = 0;
    document.getElementById('fbn-fee').value = 0;
    document.getElementById('fbn-other').value = 0;
    document.getElementById('fbn-cash').value = 0;
    document.getElementById('fbn-asset').value = 0;
    document.getElementById('fbn-rate').value = 1;
    document.getElementById('fbn-rate-row').style.display = 'none';
    document.getElementById('fbn-validation').innerHTML = '';
}

async function onFBNAccountChange() {
    const select = document.getElementById('fbn-account');
    const selectedOption = select.options[select.selectedIndex];
    const currency = selectedOption.dataset.currency;
    const date = document.getElementById('fbn-date').value;
    const account = select.value;

    // Show/hide rate field based on currency
    document.getElementById('fbn-rate-row').style.display = currency === 'USD' ? 'flex' : 'none';

    // Load existing entry if available
    if (date && account) {
        try {
            const entry = await api(`/fbn/entry/${date}/${encodeURIComponent(account)}`);
            if (entry) {
                document.getElementById('fbn-investment').value = entry.investment || 0;
                document.getElementById('fbn-deposit').value = entry.deposit || 0;
                document.getElementById('fbn-interest').value = entry.interest || 0;
                document.getElementById('fbn-dividend').value = entry.dividend || 0;
                document.getElementById('fbn-distribution').value = entry.distribution || 0;
                document.getElementById('fbn-tax').value = entry.tax || 0;
                document.getElementById('fbn-fee').value = entry.fee || 0;
                document.getElementById('fbn-other').value = entry.other || 0;
                document.getElementById('fbn-cash').value = entry.cash || 0;
                document.getElementById('fbn-asset').value = entry.asset || 0;
                document.getElementById('fbn-rate').value = entry.rate || 1;
            } else {
                resetFBNForm();
                // Keep rate field visibility
                document.getElementById('fbn-rate-row').style.display = currency === 'USD' ? 'flex' : 'none';
            }
        } catch (err) {
            // Entry doesn't exist, reset form
            resetFBNForm();
            document.getElementById('fbn-rate-row').style.display = currency === 'USD' ? 'flex' : 'none';
        }
    }

    updateFBNValidation();
}

function updateFBNValidation() {
    const investment = parseFloat(document.getElementById('fbn-investment').value) || 0;
    const deposit = parseFloat(document.getElementById('fbn-deposit').value) || 0;
    const interest = parseFloat(document.getElementById('fbn-interest').value) || 0;
    const dividend = parseFloat(document.getElementById('fbn-dividend').value) || 0;
    const distribution = parseFloat(document.getElementById('fbn-distribution').value) || 0;
    const tax = parseFloat(document.getElementById('fbn-tax').value) || 0;
    const fee = parseFloat(document.getElementById('fbn-fee').value) || 0;
    const other = parseFloat(document.getElementById('fbn-other').value) || 0;
    const cash = parseFloat(document.getElementById('fbn-cash').value) || 0;
    const asset = parseFloat(document.getElementById('fbn-asset').value) || 0;

    const variationEncaisse = investment + deposit + interest + dividend + distribution + tax + fee + other;
    const totalPlacements = asset - cash;

    document.getElementById('fbn-validation').innerHTML = `
        <div>Variation Encaisse: <strong>${fmt(variationEncaisse)}</strong></div>
        <div>Total Placements: <strong>${fmt(totalPlacements)}</strong></div>
    `;
}

async function submitFBNEntry(event) {
    event.preventDefault();

    const select = document.getElementById('fbn-account');
    const selectedOption = select.options[select.selectedIndex];

    const entry = {
        date: document.getElementById('fbn-date').value,
        account: select.value,
        portfolio: selectedOption.dataset.portfolio,
        currency: selectedOption.dataset.currency,
        investment: parseFloat(document.getElementById('fbn-investment').value) || 0,
        deposit: parseFloat(document.getElementById('fbn-deposit').value) || 0,
        interest: parseFloat(document.getElementById('fbn-interest').value) || 0,
        dividend: parseFloat(document.getElementById('fbn-dividend').value) || 0,
        distribution: parseFloat(document.getElementById('fbn-distribution').value) || 0,
        tax: parseFloat(document.getElementById('fbn-tax').value) || 0,
        fee: parseFloat(document.getElementById('fbn-fee').value) || 0,
        other: parseFloat(document.getElementById('fbn-other').value) || 0,
        cash: parseFloat(document.getElementById('fbn-cash').value) || 0,
        asset: parseFloat(document.getElementById('fbn-asset').value) || 0,
        rate: parseFloat(document.getElementById('fbn-rate').value) || 1
    };

    try {
        await api('/fbn/entry', {
            method: 'POST',
            body: JSON.stringify(entry)
        });
        showToast(`Entry saved for ${entry.account}`, 'success');
        closeFBNEntryModal();
        // Reload current view
        if (currentView === 'fbn') {
            loadFBNMonthlyStats();
        }
    } catch (err) {
        showToast(err.message || 'Failed to save entry', 'error');
    }
}

// Add validation listeners to FBN form fields
document.addEventListener('DOMContentLoaded', () => {
    const fbnFields = ['fbn-investment', 'fbn-deposit', 'fbn-interest', 'fbn-dividend',
                       'fbn-distribution', 'fbn-tax', 'fbn-fee', 'fbn-other', 'fbn-cash', 'fbn-asset'];
    fbnFields.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('input', updateFBNValidation);
        }
    });

    // Also trigger account change when date changes
    const dateEl = document.getElementById('fbn-date');
    if (dateEl) {
        dateEl.addEventListener('change', onFBNAccountChange);
    }
});

// Close modals on escape
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeModal();
        closeEditModal();
        closeFBNEntryModal();
    }
});

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    showIBKR();
});
