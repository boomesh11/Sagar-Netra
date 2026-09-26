/**
 * SagarNetra Operations Dashboard - Client Application
 * SIH 2026 Problem Statement 26057 (NIOT / MoES)
 */

(function () {
    'use strict';

    // Application State
    const state = {
        activeTab: 'mission-control',
        ws: null,
        wsConnected: false,
        pingCount: 1482,
        isWaterfallPaused: false,
        targets: [],
        selectedTarget: null,
        surveyId: 'SRV_CHENNAI_01',
        labParams: {
            preset: 'East Coast Sand',
            netLength: 15.0,
            burial: 45,
            range: 28.0,
            altitude: 8.0,
            snr: 18.0
        }
    };

    // DOM Elements Cache
    const el = {
        navTabs: document.querySelectorAll('.nav-tab'),
        tabPanes: document.querySelectorAll('.tab-pane'),

        // Mission Control
        waterfallCanvas: document.getElementById('waterfallCanvas'),
        navMapCanvas: document.getElementById('navMapCanvas'),
        btnToggleWaterfall: document.getElementById('btnToggleWaterfall'),
        metricPings: document.getElementById('metricPings'),
        metricHazards: document.getElementById('metricHazards'),

        // Target Inspector
        targetList: document.getElementById('targetList'),
        inspectorTargetTitle: document.getElementById('inspectorTargetTitle'),
        inspectorCoords: document.getElementById('inspectorCoords'),
        inspectorR95: document.getElementById('inspectorR95'),
        inspectorDims: document.getElementById('inspectorDims'),
        inspectorCropCanvas: document.getElementById('inspectorCropCanvas'),
        inspectorProfileCanvas: document.getElementById('inspectorProfileCanvas'),
        rulesTableBody: document.getElementById('rulesTableBody'),
        barLogit: document.getElementById('barLogit'),
        barObs: document.getElementById('barObs'),
        barPhys: document.getElementById('barPhys'),
        barNet: document.getElementById('barNet'),
        barViews: document.getElementById('barViews'),
        btnConfirmTarget: document.getElementById('btnConfirmTarget'),
        btnReclassifyTarget: document.getElementById('btnReclassifyTarget'),
        btnRejectTarget: document.getElementById('btnRejectTarget'),
        btnUnsureTarget: document.getElementById('btnUnsureTarget'),

        // Coverage & Clearance
        coverageCanvas: document.getElementById('coverageCanvas'),
        btnExportSecondLook: document.getElementById('btnExportSecondLook'),

        // Disaster Mode
        swipeContainer: document.getElementById('swipeContainer'),
        swipeSlider: document.getElementById('swipeSlider'),
        disasterBaseCanvas: document.getElementById('disasterBaseCanvas'),
        disasterPostCanvas: document.getElementById('disasterPostCanvas'),
        postSwipeBox: document.getElementById('postSwipeBox'),
        selDisasterScenario: document.getElementById('selDisasterScenario'),
        btnRunChangeDetect: document.getElementById('btnRunChangeDetect'),
        disasterObsCount: document.getElementById('disasterObsCount'),
        disasterList: document.getElementById('disasterList'),

        // SonarForge Lab
        labPreset: document.getElementById('labPreset'),
        sliderNetLen: document.getElementById('sliderNetLen'),
        sliderBurial: document.getElementById('sliderBurial'),
        sliderRange: document.getElementById('sliderRange'),
        sliderAltitude: document.getElementById('sliderAltitude'),
        sliderSNR: document.getElementById('sliderSNR'),
        valNetLen: document.getElementById('valNetLen'),
        valBurial: document.getElementById('valBurial'),
        valRange: document.getElementById('valRange'),
        valAltitude: document.getElementById('valAltitude'),
        valSNR: document.getElementById('valSNR'),
        btnSimulatePing: document.getElementById('btnSimulatePing'),
        labShadowFormula: document.getElementById('labShadowFormula'),
        labCanvas: document.getElementById('labCanvas'),
        labPodCanvas: document.getElementById('labPodCanvas'),

        // Reports
        manifestTableBody: document.getElementById('manifestTableBody')
    };

    // Initialize Application
    function init() {
        setupNavigation();
        initWaterfall();
        initNavMap();
        initCoverageMap();
        initDisasterMode();
        initSonarForgeLab();
        seedDefaultTargets();
        initWebSocket();
    }

    // Navigation setup
    function setupNavigation() {
        el.navTabs.forEach(tab => {
            tab.addEventListener('click', () => {
                const targetTab = tab.dataset.tab;
                switchTab(targetTab);
            });
        });
    }

    function switchTab(tabId) {
        state.activeTab = tabId;
        el.navTabs.forEach(t => t.classList.toggle('active', t.dataset.tab === tabId));
        el.tabPanes.forEach(p => p.classList.toggle('active', p.id === `pane-${tabId}`));

        if (tabId === 'coverage-clearance') renderCoverageCanvas();
        if (tabId === 'disaster-compare') renderDisasterCanvases();
        if (tabId === 'sonarforge-lab') renderLabCanvases();
        if (tabId === 'target-inspector' && state.selectedTarget) renderInspector(state.selectedTarget);
    }

    // --- SCREEN 1: WATERFALL & NAV MAP ---
    let waterfallCtx = null;
    function initWaterfall() {
        if (!el.waterfallCanvas) return;
        waterfallCtx = el.waterfallCanvas.getContext('2d');
        waterfallCtx.fillStyle = '#050c18';
        waterfallCtx.fillRect(0, 0, el.waterfallCanvas.width, el.waterfallCanvas.height);

        // Pre-fill initial acoustic waterfall lines
        for (let i = 0; i < el.waterfallCanvas.height; i++) {
            renderWaterfallLine();
        }

        el.btnToggleWaterfall?.addEventListener('click', () => {
            state.isWaterfallPaused = !state.isWaterfallPaused;
            el.btnToggleWaterfall.textContent = state.isWaterfallPaused ? 'Resume Stream' : 'Pause Stream';
        });

        // Waterfall animation timer (fallback when ws idle)
        setInterval(() => {
            if (!state.isWaterfallPaused) {
                renderWaterfallLine();
                state.pingCount++;
                if (el.metricPings) el.metricPings.textContent = state.pingCount.toLocaleString();
            }
        }, 80);
    }

    function renderWaterfallLine(stbdSamples, portSamples) {
        if (!waterfallCtx || !el.waterfallCanvas) return;
        const w = el.waterfallCanvas.width;
        const h = el.waterfallCanvas.height;

        // Shift down by 1px
        const img = waterfallCtx.getImageData(0, 0, w, h - 1);
        waterfallCtx.putImageData(img, 0, 1);

        // Top line
        const line = waterfallCtx.createImageData(w, 1);
        const center = Math.floor(w / 2);
        const nadirWidth = Math.floor(w * 0.08);

        for (let x = 0; x < w; x++) {
            const dist = Math.abs(x - center);
            let val = 0;
            if (dist < nadirWidth) {
                val = 0.03 + Math.random() * 0.03; // Water column / nadir gap
            } else {
                const normDist = (dist - nadirWidth) / (center - nadirWidth);
                const decay = Math.cos(normDist * (Math.PI / 2.3));
                const ripple = Math.sin(x * 0.12 + state.pingCount * 0.05) * 0.06;
                val = Math.max(0.02, Math.min(0.98, (0.32 + ripple + (Math.random() - 0.5) * 0.07) * decay));

                // Occasional highlight & shadow injection for live demo
                if (state.pingCount % 120 > 95 && Math.abs(x - (center + 120)) < 6) {
                    val = 0.95; // Target highlight
                } else if (state.pingCount % 120 > 95 && (x > center + 126 && x < center + 155)) {
                    val = 0.01; // Acoustic shadow
                }
            }

            const p = Math.floor(val * 255);
            const idx = x * 4;
            // Copper / Amber side-scan colormap
            line.data[idx] = Math.min(255, Math.floor(p * 1.15));
            line.data[idx + 1] = Math.min(255, Math.floor(p * 0.78));
            line.data[idx + 2] = Math.min(255, Math.floor(p * 0.32));
            line.data[idx + 3] = 255;
        }

        waterfallCtx.putImageData(line, 0, 0);
    }

    let navMapCtx = null;
    function initNavMap() {
        if (!el.navMapCanvas) return;
        navMapCtx = el.navMapCanvas.getContext('2d');
        renderNavMap();
    }

    function renderNavMap() {
        if (!navMapCtx || !el.navMapCanvas) return;
        const w = el.navMapCanvas.width;
        const h = el.navMapCanvas.height;

        navMapCtx.fillStyle = '#071526';
        navMapCtx.fillRect(0, 0, w, h);

        // Grid lines
        navMapCtx.strokeStyle = 'rgba(0, 212, 178, 0.12)';
        navMapCtx.lineWidth = 1;
        for (let x = 40; x < w; x += 40) {
            navMapCtx.beginPath();
            navMapCtx.moveTo(x, 0);
            navMapCtx.lineTo(x, h);
            navMapCtx.stroke();
        }
        for (let y = 40; y < h; y += 40) {
            navMapCtx.beginPath();
            navMapCtx.moveTo(0, y);
            navMapCtx.lineTo(w, y);
            navMapCtx.stroke();
        }

        // Survey Area Box
        navMapCtx.strokeStyle = 'rgba(0, 212, 178, 0.4)';
        navMapCtx.setLineDash([4, 4]);
        navMapCtx.strokeRect(30, 30, w - 60, h - 60);
        navMapCtx.setLineDash([]);

        // Survey track (lawnmower pattern)
        navMapCtx.strokeStyle = '#2ED573';
        navMapCtx.lineWidth = 2;
        navMapCtx.beginPath();
        const pts = [
            { x: 50, y: 60 }, { x: w - 50, y: 60 },
            { x: w - 50, y: 130 }, { x: 50, y: 130 },
            { x: 50, y: 200 }, { x: w - 50, y: 200 },
            { x: w - 50, y: 270 }, { x: 50, y: 270 },
            { x: 50, y: 340 }, { x: w - 50, y: 340 }
        ];
        pts.forEach((p, idx) => {
            if (idx === 0) navMapCtx.moveTo(p.x, p.y);
            else navMapCtx.lineTo(p.x, p.y);
        });
        navMapCtx.stroke();

        // Towfish live icon & swath cone
        const fish = { x: 220, y: 270 };
        navMapCtx.fillStyle = 'rgba(0, 212, 178, 0.2)';
        navMapCtx.beginPath();
        navMapCtx.moveTo(fish.x, fish.y);
        navMapCtx.lineTo(fish.x - 35, fish.y + 40);
        navMapCtx.lineTo(fish.x + 35, fish.y + 40);
        navMapCtx.closePath();
        navMapCtx.fill();

        navMapCtx.fillStyle = '#00D4B2';
        navMapCtx.beginPath();
        navMapCtx.arc(fish.x, fish.y, 6, 0, Math.PI * 2);
        navMapCtx.fill();
        navMapCtx.strokeStyle = '#FFFFFF';
        navMapCtx.lineWidth = 2;
        navMapCtx.stroke();

        // Target pins with r95 error circles
        state.targets.forEach((tgt, i) => {
            const tx = 70 + ((i * 110) % (w - 140));
            const ty = 80 + ((i * 85) % (h - 160));

            // r95 uncertainty circle
            navMapCtx.fillStyle = 'rgba(255, 71, 87, 0.15)';
            navMapCtx.strokeStyle = 'rgba(255, 71, 87, 0.6)';
            navMapCtx.lineWidth = 1;
            navMapCtx.beginPath();
            navMapCtx.arc(tx, ty, 14, 0, Math.PI * 2);
            navMapCtx.fill();
            navMapCtx.stroke();

            // Center pin
            navMapCtx.fillStyle = tgt.status === 'CONFIRMED_HAZARD' ? '#FF4757' : '#FFA502';
            navMapCtx.beginPath();
            navMapCtx.arc(tx, ty, 4, 0, Math.PI * 2);
            navMapCtx.fill();

            // Label
            navMapCtx.font = '10px JetBrains Mono, monospace';
            navMapCtx.fillStyle = '#E8F1F5';
            navMapCtx.fillText(tgt.id, tx + 12, ty + 3);
        });
    }

    // --- SCREEN 2: TARGET INSPECTOR ---
    function renderInspector(tgt) {
        state.selectedTarget = tgt;
        if (el.inspectorTargetTitle) {
            el.inspectorTargetTitle.textContent = `${tgt.id} — ${formatClass(tgt.class_name)} (${tgt.confidence}%)`;
        }
        if (el.inspectorCoords) {
            el.inspectorCoords.textContent = `${tgt.lat.toFixed(6)}°N, ${tgt.lon.toFixed(6)}°E`;
        }
        if (el.inspectorR95) {
            el.inspectorR95.textContent = `±${tgt.r95_m.toFixed(2)} m (${tgt.method || 'Catenary+UTM'})`;
        }
        if (el.inspectorDims) {
            el.inspectorDims.textContent = `L: ${tgt.length_m.toFixed(1)}m × W: ${tgt.width_m.toFixed(1)}m × H: ${tgt.height_m.toFixed(2)}m (Shadow Ls: ${tgt.shadow_len_m.toFixed(1)}m)`;
        }

        // Confidence component bars
        setBar(el.barLogit, tgt.components.p_cal);
        setBar(el.barObs, tgt.components.q_obs);
        setBar(el.barPhys, tgt.components.v_phys);
        setBar(el.barNet, tgt.components.s_net);
        setBar(el.barViews, tgt.components.views_score || 0.67);

        renderTargetCropCanvas(tgt);
        renderTargetProfileCanvas(tgt);
        renderRulesTable(tgt);
    }

    function setBar(bar, val) {
        if (!bar) return;
        const pct = Math.round(Math.max(0, Math.min(1, val)) * 100);
        bar.style.width = `${pct}%`;
    }

    function renderTargetCropCanvas(tgt) {
        if (!el.inspectorCropCanvas) return;
        const ctx = el.inspectorCropCanvas.getContext('2d');
        const w = el.inspectorCropCanvas.width;
        const h = el.inspectorCropCanvas.height;

        ctx.fillStyle = '#050c18';
        ctx.fillRect(0, 0, w, h);

        const cx = w / 2;
        const cy = h / 2;

        // Ambient seafloor speckle
        for (let i = 0; i < 300; i++) {
            ctx.fillStyle = `rgba(180, 140, 80, ${Math.random() * 0.12})`;
            ctx.fillRect(Math.random() * w, Math.random() * h, 3, 2);
        }

        // Acoustic highlight
        const grad = ctx.createRadialGradient(cx - 25, cy, 3, cx - 25, cy, 30);
        grad.addColorStop(0, '#FFEAA7');
        grad.addColorStop(0.6, '#E17055');
        grad.addColorStop(1, 'transparent');
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.ellipse(cx - 25, cy, 28, 14, 0, 0, Math.PI * 2);
        ctx.fill();

        // Acoustic shadow
        ctx.fillStyle = '#02050A';
        ctx.beginPath();
        ctx.moveTo(cx - 10, cy - 12);
        ctx.lineTo(cx + 65, cy - 20);
        ctx.lineTo(cx + 65, cy + 20);
        ctx.lineTo(cx - 10, cy + 12);
        ctx.closePath();
        ctx.fill();

        ctx.strokeStyle = 'rgba(0, 212, 178, 0.5)';
        ctx.setLineDash([3, 3]);
        ctx.stroke();
        ctx.setLineDash([]);

        ctx.font = '10px JetBrains Mono, monospace';
        ctx.fillStyle = '#FFEAA7';
        ctx.fillText(`HIGHLIGHT (L=${tgt.length_m}m)`, cx - 80, cy - 24);

        ctx.fillStyle = '#00D4B2';
        ctx.fillText(`SHADOW (Ls=${tgt.shadow_len_m}m -> H=${tgt.height_m}m)`, cx + 10, cy + 34);
    }

    function renderTargetProfileCanvas(tgt) {
        if (!el.inspectorProfileCanvas) return;
        const ctx = el.inspectorProfileCanvas.getContext('2d');
        const w = el.inspectorProfileCanvas.width;
        const h = el.inspectorProfileCanvas.height;

        ctx.fillStyle = '#071526';
        ctx.fillRect(0, 0, w, h);

        // Baseline axes
        ctx.strokeStyle = 'rgba(255,255,255,0.15)';
        ctx.beginPath();
        ctx.moveTo(25, 15);
        ctx.lineTo(25, h - 20);
        ctx.lineTo(w - 15, h - 20);
        ctx.stroke();

        // Target profile line
        ctx.strokeStyle = '#00D4B2';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(30, h - 30);
        ctx.lineTo(65, h - 30);
        // Highlight peak
        ctx.bezierCurveTo(80, h - 30, 90, 25, 105, 25);
        ctx.bezierCurveTo(120, 25, 125, h - 12, 140, h - 12);
        // Shadow trough
        ctx.lineTo(190, h - 12);
        // Seabed return
        ctx.bezierCurveTo(200, h - 12, 210, h - 30, 230, h - 30);
        ctx.lineTo(w - 20, h - 30);
        ctx.stroke();

        // Annotations
        ctx.fillStyle = '#FF4757';
        ctx.beginPath();
        ctx.arc(105, 25, 3.5, 0, Math.PI * 2);
        ctx.fill();

        ctx.font = '10px Outfit, sans-serif';
        ctx.fillStyle = '#E8F1F5';
        ctx.fillText(`Peak Height: +${tgt.height_m}m`, 112, 28);
    }

    function renderRulesTable(tgt) {
        if (!el.rulesTableBody) return;
        const rules = [
            { id: 'R1', name: 'Class Height Prior', cond: 'h <= 1.5m for net', val: `${tgt.height_m}m`, pass: tgt.height_m <= 1.5 },
            { id: 'R2', name: 'Highlight Before Shadow', cond: 'x_shadow > x_hl', val: 'Consistent down-range', pass: true },
            { id: 'R3', name: 'Port/Stbd Interference Veto', cond: 'No mirror on opp. side', val: 'Unilateral detection', pass: true },
            { id: 'R4', name: 'Along-track Footprint Persistence', cond: 'Spans >= 3 pings', val: '7 consecutive pings', pass: true },
            { id: 'R5', name: 'Water-Column Blind Zone Veto', cond: 'Range >= Nadir altitude', val: '28.4m > 8.1m alt', pass: true },
            { id: 'R6', name: 'Surface Multipath Mask', cond: 'Range != 2x Depth', val: 'Clear of surface zone', pass: true },
            { id: 'R7', name: 'Resolution Adequacy Check', cond: 'Along-track px >= 3', val: 'Adequate grazing (18°)', pass: true },
            { id: 'R8', name: 'Seafloor Slope Instability', cond: 'Local seabed slope < 5°', val: 'Slope 1.4° (stable)', pass: true }
        ];

        el.rulesTableBody.innerHTML = rules.map(r => `
            <tr>
                <td style="font-weight:700; color:#00D4B2;">${r.id}</td>
                <td>${r.name}</td>
                <td style="color:#8FA3BF;">${r.cond}</td>
                <td>${r.val}</td>
                <td><span class="badge ${r.pass ? 'badge-confirmed' : 'badge-hazard'}">${r.pass ? 'PASS' : 'FAIL'}</span></td>
            </tr>
        `).join('');
    }

    // --- SCREEN 3: COVERAGE & CLEARANCE ---
    function initCoverageMap() {
        el.btnExportSecondLook?.addEventListener('click', () => {
            alert('Autonomous Second-Look Track SL_TGT_0001 exported as GeoJSON & GPX waypoints.');
        });
    }

    function renderCoverageCanvas() {
        if (!el.coverageCanvas) return;
        const ctx = el.coverageCanvas.getContext('2d');
        const w = el.coverageCanvas.width;
        const h = el.coverageCanvas.height;

        ctx.fillStyle = '#071526';
        ctx.fillRect(0, 0, w, h);

        const rows = 20;
        const cols = 26;
        const cellW = (w - 60) / cols;
        const cellH = (h - 60) / rows;

        for (let r = 0; r < rows; r++) {
            for (let c = 0; c < cols; c++) {
                let pod = 0.92 - Math.abs(Math.sin(c * 0.4)) * 0.14;
                if (c >= 12 && c <= 14 && r >= 6 && r <= 14) {
                    pod = 0.48; // Inadequate gap in middle pass
                }

                let color = '#2ED573';
                if (pod >= 0.80) color = '#2ED573';
                else if (pod >= 0.50) color = '#FFA502';
                else color = '#FF4757';

                ctx.fillStyle = color;
                ctx.globalAlpha = 0.75;
                ctx.fillRect(30 + c * cellW, 30 + r * cellH, cellW - 1, cellH - 1);
            }
        }
        ctx.globalAlpha = 1.0;

        // Second-look infill line
        const gapX = 30 + 13 * cellW;
        ctx.strokeStyle = '#00D4B2';
        ctx.lineWidth = 3;
        ctx.setLineDash([6, 4]);
        ctx.beginPath();
        ctx.moveTo(gapX, 30 + 5 * cellH);
        ctx.lineTo(gapX, 30 + 15 * cellH);
        ctx.stroke();
        ctx.setLineDash([]);

        ctx.font = '10px JetBrains Mono, monospace';
        ctx.fillStyle = '#00D4B2';
        ctx.fillText('AUTONOMOUS SECOND-LOOK LINE (Track SL_01)', gapX - 110, 30 + 4 * cellH);
    }

    // --- SCREEN 4: DISASTER MODE ---
    function initDisasterMode() {
        if (!el.swipeSlider || !el.postSwipeBox) return;

        el.swipeSlider.addEventListener('input', (e) => {
            const pct = e.target.value;
            el.postSwipeBox.style.clipPath = `polygon(${pct}% 0, 100% 0, 100% 100%, ${pct}% 100%)`;
        });

        el.btnRunChangeDetect?.addEventListener('click', () => {
            alert('Running sub-pixel registration & log-ratio change detection on Cyclone Michaung survey pair...');
            renderDisasterCanvases();
        });
    }

    function renderDisasterCanvases() {
        renderDisasterBase();
        renderDisasterPost();
        populateDisasterList();
    }

    function renderDisasterBase() {
        if (!el.disasterBaseCanvas) return;
        const ctx = el.disasterBaseCanvas.getContext('2d');
        const w = el.disasterBaseCanvas.width;
        const h = el.disasterBaseCanvas.height;

        ctx.fillStyle = '#050c18';
        ctx.fillRect(0, 0, w, h);

        // Smooth sandy harbour floor
        for (let y = 0; y < h; y += 4) {
            for (let x = 0; x < w; x += 4) {
                const val = 0.28 + Math.sin(x * 0.05 + y * 0.02) * 0.04 + (Math.random() - 0.5) * 0.03;
                const p = Math.floor(val * 255);
                ctx.fillStyle = `rgb(${p * 1.1}, ${p * 0.75}, ${p * 0.3})`;
                ctx.fillRect(x, y, 4, 4);
            }
        }
    }

    function renderDisasterPost() {
        if (!el.disasterPostCanvas) return;
        const ctx = el.disasterPostCanvas.getContext('2d');
        const w = el.disasterPostCanvas.width;
        const h = el.disasterPostCanvas.height;

        // Base
        ctx.fillStyle = '#050c18';
        ctx.fillRect(0, 0, w, h);

        for (let y = 0; y < h; y += 4) {
            for (let x = 0; x < w; x += 4) {
                const val = 0.28 + Math.sin(x * 0.05 + y * 0.02) * 0.04 + (Math.random() - 0.5) * 0.03;
                const p = Math.floor(val * 255);
                ctx.fillStyle = `rgb(${p * 1.1}, ${p * 0.75}, ${p * 0.3})`;
                ctx.fillRect(x, y, 4, 4);
            }
        }

        // Inject new obstruction: Sunken container at (cx, cy)
        const cx = 320;
        const cy = 210;
        ctx.fillStyle = '#FFEAA7';
        ctx.fillRect(cx - 35, cy - 10, 45, 20);

        // Shadow behind container
        ctx.fillStyle = '#02050A';
        ctx.beginPath();
        ctx.moveTo(cx + 10, cy - 10);
        ctx.lineTo(cx + 90, cy - 15);
        ctx.lineTo(cx + 90, cy + 25);
        ctx.lineTo(cx + 10, cy + 10);
        ctx.closePath();
        ctx.fill();

        // Highlight box
        ctx.strokeStyle = '#FF4757';
        ctx.lineWidth = 2;
        ctx.strokeRect(cx - 40, cy - 15, 140, 45);

        ctx.font = '10px JetBrains Mono, monospace';
        ctx.fillStyle = '#FF4757';
        ctx.fillText('NEW OBSTRUCTION: CONTAINER #01', cx - 40, cy - 20);
    }

    function populateDisasterList() {
        if (!el.disasterList) return;
        const diffs = [
            { type: 'NEW_OBSTRUCTION', desc: 'Displaced 40ft Shipping Container', pos: '13.0829°N, 80.2711°E', conf: '94.2%', r95: '±2.1m' },
            { type: 'NEW_OBSTRUCTION', desc: 'Sunken Wooden Trawler Fragment', pos: '13.0815°N, 80.2698°E', conf: '88.5%', r95: '±3.4m' }
        ];

        el.disasterList.innerHTML = diffs.map(d => `
            <div class="disaster-card">
                <div class="card-head">
                    <span class="badge badge-hazard">${d.type}</span>
                    <span class="conf-text">${d.conf} Conf</span>
                </div>
                <div class="card-desc">${d.desc}</div>
                <div class="card-meta">Pos: ${d.pos} (r95: ${d.r95})</div>
            </div>
        `).join('');
    }

    // --- SCREEN 5: SONARFORGE LAB ---
    function initSonarForgeLab() {
        const updateParams = () => {
            state.labParams.preset = el.labPreset?.value || 'East Coast Sand';
            state.labParams.netLength = parseFloat(el.sliderNetLen?.value || 15);
            state.labParams.burial = parseFloat(el.sliderBurial?.value || 45);
            state.labParams.range = parseFloat(el.sliderRange?.value || 28);
            state.labParams.altitude = parseFloat(el.sliderAltitude?.value || 8);
            state.labParams.snr = parseFloat(el.sliderSNR?.value || 18);

            if (el.valNetLen) el.valNetLen.textContent = `${state.labParams.netLength.toFixed(1)}m`;
            if (el.valBurial) el.valBurial.textContent = `${state.labParams.burial}%`;
            if (el.valRange) el.valRange.textContent = `${state.labParams.range.toFixed(1)}m`;
            if (el.valAltitude) el.valAltitude.textContent = `${state.labParams.altitude.toFixed(1)}m`;
            if (el.valSNR) el.valSNR.textContent = `${state.labParams.snr.toFixed(1)} dB`;

            // Calculate shadow length by acoustic ray geometry: Ls = h * xo / (H - h)
            const h_target = 0.85 * (1 - state.labParams.burial / 100);
            const ls = (h_target * state.labParams.range) / Math.max(0.2, (state.labParams.altitude - h_target));
            if (el.labShadowFormula) {
                el.labShadowFormula.textContent = `Shadow Lₛ = ${ls.toFixed(2)}m (H_target=${h_target.toFixed(2)}m)`;
            }

            renderLabCanvases();
        };

        el.sliderNetLen?.addEventListener('input', updateParams);
        el.sliderBurial?.addEventListener('input', updateParams);
        el.sliderRange?.addEventListener('input', updateParams);
        el.sliderAltitude?.addEventListener('input', updateParams);
        el.sliderSNR?.addEventListener('input', updateParams);
        el.labPreset?.addEventListener('change', updateParams);

        el.btnSimulatePing?.addEventListener('click', () => {
            alert('Acoustic ray physics rendered with SonarForge engine.');
            renderLabCanvases();
        });
    }

    function renderLabCanvases() {
        renderLabWaterfall();
        renderLabPoDCurve();
    }

    function renderLabWaterfall() {
        if (!el.labCanvas) return;
        const ctx = el.labCanvas.getContext('2d');
        const w = el.labCanvas.width;
        const h = el.labCanvas.height;

        ctx.fillStyle = '#050c18';
        ctx.fillRect(0, 0, w, h);

        const center = w / 2;
        const params = state.labParams;
        const nadirPx = Math.floor((params.altitude / 60.0) * center);

        const img = ctx.createImageData(w, h);
        for (let y = 0; y < h; y++) {
            for (let x = 0; x < w; x++) {
                const dist = Math.abs(x - center);
                let val = 0;
                if (dist < nadirPx) {
                    val = 0.03 + Math.random() * 0.02;
                } else {
                    const ripple = Math.sin(x * 0.15 + y * 0.05) * 0.05;
                    val = Math.max(0.02, 0.32 + ripple + (Math.random() - 0.5) * 0.06);
                }

                // Inject synthetic net
                const tgtX = center + Math.floor((params.range / 60.0) * center);
                const tgtY = Math.floor(h / 2);
                if (Math.abs(y - tgtY) < (params.netLength * 1.5)) {
                    if (Math.abs(x - tgtX) < 4) {
                        val = 0.90 * (1 - params.burial / 150); // Highlight
                    } else if (x > tgtX + 4 && x < tgtX + 4 + (20 * (1 - params.burial / 100))) {
                        val = 0.01; // Shadow
                    }
                }

                const p = Math.floor(Math.min(1.0, val) * 255);
                const idx = (y * w + x) * 4;
                lineColormap(img.data, idx, p);
            }
        }
        ctx.putImageData(img, 0, 0);
    }

    function lineColormap(data, idx, p) {
        data[idx] = Math.min(255, Math.floor(p * 1.15));
        data[idx + 1] = Math.min(255, Math.floor(p * 0.78));
        data[idx + 2] = Math.min(255, Math.floor(p * 0.32));
        data[idx + 3] = 255;
    }

    function renderLabPoDCurve() {
        if (!el.labPodCanvas) return;
        const ctx = el.labPodCanvas.getContext('2d');
        const w = el.labPodCanvas.width;
        const h = el.labPodCanvas.height;

        ctx.fillStyle = '#071526';
        ctx.fillRect(0, 0, w, h);

        // Axes
        ctx.strokeStyle = 'rgba(255,255,255,0.15)';
        ctx.beginPath();
        ctx.moveTo(35, 20);
        ctx.lineTo(35, h - 25);
        ctx.lineTo(w - 20, h - 25);
        ctx.stroke();

        // 80% PoD clearance threshold line
        const y80 = 20 + (1 - 0.80) * (h - 45);
        ctx.strokeStyle = 'rgba(46, 213, 115, 0.4)';
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(35, y80);
        ctx.lineTo(w - 20, y80);
        ctx.stroke();
        ctx.setLineDash([]);

        // PoD curve vs Range
        ctx.strokeStyle = '#00D4B2';
        ctx.lineWidth = 2.5;
        ctx.beginPath();

        const maxRange = 60.0;
        const burialFactor = 1.0 - (state.labParams.burial / 100) * 0.25;

        for (let r = 0; r <= maxRange; r += 1) {
            const x = 35 + (r / maxRange) * (w - 55);
            let pod = (0.95 * burialFactor) / (1.0 + Math.exp((r - 42.0) * 0.18));
            if (r < state.labParams.altitude) pod = 0.12; // Nadir blind zone

            const y = 20 + (1 - pod) * (h - 45);
            if (r === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }
        ctx.stroke();

        ctx.font = '9px JetBrains Mono, monospace';
        ctx.fillStyle = '#2ED573';
        ctx.fillText('80% CLEARANCE THRESHOLD', w - 165, y80 - 5);
        ctx.fillStyle = '#8FA3BF';
        ctx.fillText('Range (0m -> 60m)', w / 2 - 30, h - 8);
    }

    // --- SEED TARGETS & MANIFEST ---
    function seedDefaultTargets() {
        state.targets = [
            {
                id: 'TGT_0001',
                rank: 1,
                class_name: 'ghost_net',
                status: 'CONFIRMED_HAZARD',
                confidence: 89,
                priority: 'CRITICAL',
                lat: 13.082745,
                lon: 80.270720,
                r95_m: 1.84,
                length_m: 18.5,
                width_m: 2.2,
                height_m: 1.15,
                shadow_len_m: 5.4,
                components: { p_cal: 0.91, q_obs: 0.94, v_phys: 0.88, s_net: 0.89, views_score: 0.75 }
            },
            {
                id: 'TGT_0002',
                rank: 2,
                class_name: 'wreck_debris',
                status: 'CONFIRMED_HAZARD',
                confidence: 94,
                priority: 'HIGH',
                lat: 13.083510,
                lon: 80.271840,
                r95_m: 2.45,
                length_m: 12.2,
                width_m: 2.4,
                height_m: 2.60,
                shadow_len_m: 9.8,
                components: { p_cal: 0.96, q_obs: 0.92, v_phys: 0.95, s_net: 0.20, views_score: 0.85 }
            },
            {
                id: 'TGT_0003',
                rank: 3,
                class_name: 'cylinder',
                status: 'CANDIDATE',
                confidence: 76,
                priority: 'MEDIUM',
                lat: 13.081920,
                lon: 80.269450,
                r95_m: 3.12,
                length_m: 1.8,
                width_m: 0.6,
                height_m: 0.60,
                shadow_len_m: 2.8,
                components: { p_cal: 0.78, q_obs: 0.85, v_phys: 0.82, s_net: 0.15, views_score: 0.50 }
            }
        ];

        renderTargetList();
        renderManifestTable();
        if (state.targets.length > 0) {
            renderInspector(state.targets[0]);
        }
    }

    function renderTargetList() {
        if (!el.targetList) return;
        el.targetList.innerHTML = '';

        state.targets.forEach(tgt => {
            const card = document.createElement('div');
            card.className = `target-card ${state.selectedTarget?.id === tgt.id ? 'active' : ''}`;
            card.innerHTML = `
                <div class="card-head">
                    <span class="target-id">${tgt.id}</span>
                    <span class="badge ${tgt.status === 'CONFIRMED_HAZARD' ? 'badge-hazard' : 'badge-candidate'}">${tgt.confidence}%</span>
                </div>
                <div class="card-class">${formatClass(tgt.class_name)}</div>
                <div class="card-meta">r95: ±${tgt.r95_m}m | H: ${tgt.height_m}m</div>
            `;
            card.addEventListener('click', () => {
                document.querySelectorAll('.target-card').forEach(c => c.classList.remove('active'));
                card.classList.add('active');
                renderInspector(tgt);
            });
            el.targetList.appendChild(card);
        });
    }

    function renderManifestTable() {
        if (!el.manifestTableBody) return;
        el.manifestTableBody.innerHTML = state.targets.map(t => `
            <tr>
                <td style="font-weight:700; color:#00D4B2;">#${t.rank}</td>
                <td><b>${t.id}</b></td>
                <td>${formatClass(t.class_name)}</td>
                <td><span class="badge ${t.status === 'CONFIRMED_HAZARD' ? 'badge-hazard' : 'badge-candidate'}">${t.status}</span></td>
                <td><b>${t.confidence}%</b></td>
                <td><span class="badge badge-hazard">${t.priority}</span></td>
                <td>${t.lat.toFixed(5)}°N, ${t.lon.toFixed(5)}°E</td>
                <td>±${t.r95_m.toFixed(2)} m</td>
                <td>${(2 * t.r95_m).toFixed(1)}m × ${(2 * t.r95_m).toFixed(1)}m</td>
                <td><button class="btn btn-sm btn-outline" onclick="window.open('/api/surveys/SRV_CHENNAI_01/reports/pdf', '_blank')">Work Order</button></td>
            </tr>
        `).join('');
    }

    function formatClass(raw) {
        if (!raw) return 'Unknown Object';
        return raw.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
    }

    // --- WEBSOCKET CLIENT ---
    function initWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/waterfall`;

        try {
            state.ws = new WebSocket(wsUrl);
            state.ws.onopen = () => { state.wsConnected = true; };
            state.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.ping_number) state.pingCount = data.ping_number;
                if (el.metricPings) el.metricPings.textContent = state.pingCount.toLocaleString();
            };
            state.ws.onclose = () => { state.wsConnected = false; };
            state.ws.onerror = () => { state.wsConnected = false; };
        } catch (e) {
            console.warn('Live WebSocket stream fallback to internal client loop');
        }
    }

    // Review Actions
    el.btnConfirmTarget?.addEventListener('click', () => {
        if (state.selectedTarget) {
            state.selectedTarget.status = 'CONFIRMED_HAZARD';
            alert(`${state.selectedTarget.id} confirmed as verified hazard!`);
            renderTargetList();
            renderManifestTable();
        }
    });

    el.btnRejectTarget?.addEventListener('click', () => {
        if (state.selectedTarget) {
            state.selectedTarget.status = 'REJECTED';
            alert(`${state.selectedTarget.id} rejected as false alarm.`);
            renderTargetList();
            renderManifestTable();
        }
    });

    document.addEventListener('DOMContentLoaded', init);
})();
