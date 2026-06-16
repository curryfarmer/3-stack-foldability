// app.js — top-level state, multi-grid mgmt, palette wiring, k formula.

const App = (() => {
  const state = {
    tool: 'pen',
    color: '#ee9944',
    grids: [],
    views: new Map(),     // id -> GridView
    focusedGridId: null,
    activeGroupId: null,
    nextGridNum: 1,
    preventOverlap: true,
    search: {
      worker: null,
      running: false,
      solutions: [],
      lastProgress: null,
      lastOpts: null,
      cursor: 0,
      tw0Only: false,
      decompFilter: '',
      shapeFilter: '',
      actualFilter: '',    // ''|fold|jam|untested — physical result from the joined finding
      predFilter: '',      // ''|yes|no — engine-predicted foldable (derived from candidate verdict)
      tagFilters: {},      // {tagKey: ''|true|false} — custom-tag tri-state filters
      stacks: 3,           // 3 = footprint/decomp search; 2 = RSPA HC patterns (loaded JSON)
      dims: null,          // {m,n} for 2-stack rendering
    },
    findings: { byHash: new Map(), loaded: false },   // normalizedHash -> FoldFinding (results/foldfindings.json)
    display: {
      showLabels: true,
      showVectors: true,
      showFoldArrows: true,
      showPlacements: true,
      showFootprint: true,
      showPaint: true,
      vectorSize: 10,
      placementInset: 3,
      chevronSize: 16,
    },
  };

  // Letter → color: same letter is always the same color across grids.
  const groupPalette = ['#39c', '#e94', '#7c3', '#c39', '#3c9', '#94e', '#c93', '#39e',
                        '#c3c', '#3cc', '#cc3', '#33c', '#c33', '#3c3', '#993', '#363'];
  function colorForLabel(label) {
    const idx = label.charCodeAt(0) - 65;   // A=0, B=1, ...
    return groupPalette[((idx % groupPalette.length) + groupPalette.length) % groupPalette.length];
  }
  function nextLabelForGrid(grid) {
    const used = new Set(grid.groups.map(g => g.label));
    for (let i = 0; i < 26; i++) {
      const l = String.fromCharCode(65 + i);
      if (!used.has(l)) return l;
    }
    return `G${grid.groups.length + 1}`;
  }

  // --- App API used by GridView ---
  const api = {
    get tool() { return state.tool; },
    get color() { return state.color; },
    get activeGroupId() { return state.activeGroupId; },
    get preventOverlap() { return state.preventOverlap; },
    get display() { return state.display; },

    renderAll() { for (const v of state.views.values()) v.render(); },

    activeGroup(grid) {
      return grid.groups.find(g => g.id === state.activeGroupId) || null;
    },

    focusGrid(id) {
      if (state.focusedGridId === id) return;
      state.focusedGridId = id;
      for (const v of state.views.values()) v.setFocused(v.state.id === id);
      const g = state.grids.find(x => x.id === id);
      if (g) {
        document.getElementById('mInput').value = g.m;
        document.getElementById('nInput').value = g.n;
      }
    },

    setActiveGroup(gid) {
      state.activeGroupId = gid;
      const sel = document.getElementById('activeGroupSelect');
      if (sel) sel.value = gid || '';
      for (const v of state.views.values()) v.renderCounters();
    },

    addGroup(gridId) {
      const g = state.grids.find(x => x.id === gridId);
      if (!g) return;
      const label = nextLabelForGrid(g);
      const color = colorForLabel(label);
      const group = {
        id: `${gridId}-grp-${label}`,
        label, color,
        baseCells: [],
        vectors: [],
        placements: [Fold.initialPlacement([])],
        hFolds: 0, vFolds: 0,
      };
      g.groups.push(group);
      api.setActiveGroup(group.id);
      refreshGroupSelect();
      state.views.get(gridId).render();
    },

    resetFolds(gridId) {
      const g = state.grids.find(x => x.id === gridId);
      if (!g) return;
      for (const grp of g.groups) {
        Fold.resetGroup(grp);
        Fold.syncVectors(grp);
      }
      state.views.get(gridId).render();
    },

    clearVectors(gridId) {
      const g = state.grids.find(x => x.id === gridId);
      if (!g) return;
      for (const grp of g.groups) {
        grp.vectors = [];
        Fold.syncVectors(grp);
      }
      state.views.get(gridId).render();
    },

    clearAll(gridId) {
      const g = state.grids.find(x => x.id === gridId);
      if (!g) return;
      if (!confirm('Clear all paint, footprint, groups, vectors on this grid?')) return;
      g.cells.clear();
      g.footprint.clear();
      g.groups = [];
      state.activeGroupId = null;
      refreshGroupSelect();
      state.views.get(gridId).render();
    },

    deleteGrid(gridId) {
      if (state.grids.length <= 1) { alert('Need at least one grid.'); return; }
      if (!confirm('Delete this grid?')) return;
      const idx = state.grids.findIndex(x => x.id === gridId);
      if (idx < 0) return;
      state.grids.splice(idx, 1);
      const view = state.views.get(gridId);
      view.root.remove();
      state.views.delete(gridId);
      refreshGroupSelect();
      if (state.focusedGridId === gridId) api.focusGrid(state.grids[0].id);
    },

    loadSolution(solutionId) {
      const sol = state.search.solutions.find(s => s.id === solutionId);
      if (!sol) return;
      const gridId = state.focusedGridId;
      const g = state.grids.find(x => x.id === gridId);
      if (!g) return;
      state.views.get(gridId).twoStack = null;   // leaving any 2-stack view
      const m = Math.max(...sol.footprint.cells.map(c => c.x), ...sol.chains.flatMap(c => c.baseCells.map(b => b.x))) + 1;
      const n = Math.max(...sol.footprint.cells.map(c => c.y), ...sol.chains.flatMap(c => c.baseCells.map(b => b.y))) + 1;
      // Resize grid to match solution
      g.m = Math.max(g.m, m, +document.getElementById('searchM').value);
      g.n = Math.max(g.n, n, +document.getElementById('searchN').value);
      // Override exactly to search dims to avoid drift
      g.m = +document.getElementById('searchM').value;
      g.n = +document.getElementById('searchN').value;
      g.cells.clear();
      g.footprint.clear();
      g.groups = [];
      state.activeGroupId = null;

      for (const c of sol.footprint.cells) g.footprint.add(`${c.x},${c.y}`);

      sol.chains.forEach((chain, i) => {
        const label = String.fromCharCode(65 + i);
        const color = colorForLabel(label);
        const baseCells = chain.baseCells.map(b => ({x: b.x, y: b.y}));
        const placements = [Fold.initialPlacement(baseCells)];
        let hFolds = 0, vFolds = 0;
        for (const dir of chain.foldArrows) {
          const np = Fold.makeFold(placements[placements.length - 1], dir, g.m, g.n);
          if (!np) { console.warn('loadSolution: fold failed on', dir, 'at chain', i); break; }
          placements.push(np);
          if (dir === 'L' || dir === 'R') hFolds++; else vFolds++;
        }
        g.groups.push({
          id: `${gridId}-grp-sol${sol.id}-${label}`,
          label, color,
          baseCells, vectors: [],
          placements, hFolds, vFolds,
        });
      });
      refreshGroupSelect();
      document.getElementById('mInput').value = g.m;
      document.getElementById('nInput').value = g.n;
      state.views.get(gridId).render();
    },
  };

  // --- Grid creation ---
  function newGrid(m = 6, n = 6) {
    const id = `g${state.nextGridNum++}`;
    return {
      id,
      label: `Grid ${id.slice(1)}`,
      m, n,
      cells: new Map(),
      footprint: new Set(),
      groups: [],
    };
  }

  function addGrid() {
    const g = newGrid();
    state.grids.push(g);
    const view = new GridView(g, api);
    state.views.set(g.id, view);
    document.getElementById('grids').appendChild(view.root);
    view.render();
    api.focusGrid(g.id);
    refreshGroupSelect();
  }

  // --- UI wiring ---
  function refreshGroupSelect() {
    const sel = document.getElementById('activeGroupSelect');
    sel.innerHTML = '<option value="">(none)</option>';
    for (const g of state.grids) {
      for (const grp of g.groups) {
        const opt = document.createElement('option');
        opt.value = grp.id;
        opt.textContent = `${g.label} · ${grp.label}`;
        if (grp.id === state.activeGroupId) opt.selected = true;
        sel.appendChild(opt);
      }
    }
  }

  function applyDimsToFocused() {
    const g = state.grids.find(x => x.id === state.focusedGridId);
    if (!g) return;
    const m = Math.max(1, Math.min(40, +document.getElementById('mInput').value || 1));
    const n = Math.max(1, Math.min(40, +document.getElementById('nInput').value || 1));
    g.m = m; g.n = n;
    // Drop cells/footprint outside new bounds
    for (const k of [...g.cells.keys()]) {
      const [x, y] = k.split(',').map(Number);
      if (x >= m || y >= n) g.cells.delete(k);
    }
    for (const k of [...g.footprint]) {
      const [x, y] = k.split(',').map(Number);
      if (x >= m || y >= n) g.footprint.delete(k);
    }
    for (const grp of g.groups) {
      grp.baseCells = grp.baseCells.filter(c => c.x < m && c.y < n);
      Fold.resetGroup(grp);
      Fold.syncVectors(grp);
    }
    state.views.get(g.id).render();
  }

  // --- App mode (View results vs Edit) -----------------------------------------
  // View = browse precomputed Python results (default, source of truth); Edit = manual folding.
  // The sidebar swaps #viewPanel <-> #editPanel; Display + Legend stay shared. The results
  // nav/table (in #mainCol) only belong to View mode.
  function setMode(mode) {
    const edit = mode === 'edit';
    document.getElementById('editPanel').style.display = edit ? '' : 'none';
    document.getElementById('viewPanel').style.display = edit ? 'none' : '';
    const hasSols = state.search.solutions.length > 0;
    document.getElementById('searchResults').style.display = (!edit && hasSols) ? '' : 'none';
    if (edit) document.getElementById('searchNav').style.display = 'none';
    else renderSearchNav();
  }

  // Fetch results/manifest.json, populate the grid dropdown, auto-load the latest entry.
  // Served via `python -m http.server`; on file:// or a missing manifest this no-ops so the
  // Advanced search + manual Load-JSON picker remain the usable paths.
  async function initResultsManifest() {
    const sel = document.getElementById('resultsManifestSelect');
    let entries;
    try {
      const res = await fetch('results/manifest.json');
      if (!res.ok) throw new Error(`manifest ${res.status}`);
      entries = await res.json();
    } catch (err) {
      sel.innerHTML = '<option value="">(no manifest — use Advanced search or Load JSON)</option>';
      return;
    }
    if (!Array.isArray(entries) || !entries.length) {
      sel.innerHTML = '<option value="">(manifest empty)</option>';
      return;
    }
    const sorted = entries.slice().sort((a, b) =>
      (a.m - b.m) || (a.n - b.n) || String(a.key).localeCompare(String(b.key)));
    sel.innerHTML = sorted.map(e => {
      const stacks = (e.opts && e.opts.stacks) || 3;
      return `<option value="${e.file}">${e.m}x${e.n} (${e.count}) — ${stacks}-stack</option>`;
    }).join('');
    sel.addEventListener('change', () => { if (sel.value) loadResultFile(sel.value); });
    // Auto-load the most recently generated result.
    const latest = entries.reduce((a, b) => ((a.generated || '') >= (b.generated || '') ? a : b));
    sel.value = latest.file;
    loadResultFile(latest.file);
  }

  async function loadResultFile(file) {
    try {
      const res = await fetch('results/' + file);
      if (!res.ok) throw new Error(`result ${res.status}`);
      loadResultsData(await res.json());
    } catch (err) {
      alert('Could not load result file: ' + err.message);
    }
  }

  function init() {
    // Tools
    document.querySelectorAll('input[name=tool]').forEach(r => {
      r.addEventListener('change', e => { state.tool = e.target.value; });
    });
    document.getElementById('colorPicker').addEventListener('input', e => { state.color = e.target.value; });
    document.getElementById('activeGroupSelect').addEventListener('change', e => {
      state.activeGroupId = e.target.value || null;
      for (const v of state.views.values()) v.renderCounters();
    });
    document.getElementById('addGridBtn').addEventListener('click', addGrid);
    document.getElementById('mInput').addEventListener('change', applyDimsToFocused);
    document.getElementById('nInput').addEventListener('change', applyDimsToFocused);

    document.getElementById('preventOverlapChk').addEventListener('change', e => {
      state.preventOverlap = e.target.checked;
    });
    const wireCheck = (id, key) => {
      const el = document.getElementById(id);
      if (!el) return;
      el.addEventListener('change', e => {
        state.display[key] = e.target.checked;
        api.renderAll();
      });
    };
    wireCheck('showLabelsChk', 'showLabels');
    wireCheck('showVectorsChk', 'showVectors');
    wireCheck('showFoldArrowsChk', 'showFoldArrows');
    wireCheck('showPlacementsChk', 'showPlacements');
    wireCheck('showFootprintChk', 'showFootprint');
    wireCheck('showPaintChk', 'showPaint');
    const wireRange = (id, key) => {
      document.getElementById(id).addEventListener('input', e => {
        state.display[key] = +e.target.value;
        api.renderAll();
      });
    };
    wireRange('vectorSize', 'vectorSize');
    wireRange('placementInset', 'placementInset');
    wireRange('chevronSize', 'chevronSize');

    wireSearchPanel();
    wireFindingPanel();

    // App mode: View (browse Python results) vs Edit (manual folding). View is default.
    document.querySelectorAll('input[name=appmode]').forEach(r => {
      r.addEventListener('change', e => setMode(e.target.value));
    });

    // Boot one grid, default to View mode, then auto-load the latest Python results.
    addGrid();
    setMode('view');
    initResultsManifest();
    loadFindings();   // joins onto candidates by normalized canonicalHash; silent if missing
  }

  // --- Search panel wiring ---

  function buildWorkerBlobUrl() {
    // Inline fold.js + search.js into a blob so we don't depend on importScripts URL resolution.
    // (importScripts works only when served via http://; this also works on http:// and is more robust.)
    const foldUrl = new URL('fold.js', location.href).href;
    const searchUrl = new URL('search.js', location.href).href;
    const code = `importScripts(${JSON.stringify(foldUrl)});\nimportScripts(${JSON.stringify(searchUrl)});\n`;
    const blob = new Blob([code], { type: 'application/javascript' });
    return URL.createObjectURL(blob);
  }

  function startSearch() {
    if (state.search.running) return;
    if (location.protocol === 'file:') {
      alert('Search needs the page to be served via http (e.g. `python3 -m http.server`). file:// URLs cannot spawn Workers.');
      return;
    }
    const opts = {
      m: Math.max(2, Math.min(14, +document.getElementById('searchM').value || 6)),
      n: Math.max(2, Math.min(14, +document.getElementById('searchN').value || 4)),
      shapes: {
        L: document.getElementById('searchShapeL').checked,
        Rect: document.getElementById('searchShapeRect').checked,
      },
      decomps: {
        '2+1': document.getElementById('searchDec21').checked,
        '1+1+1': document.getElementById('searchDec111').checked,
      },
      allowNonCorner: document.getElementById('searchAllowNonCorner').checked,
      dedup: document.getElementById('searchDedup').checked,
    };
    state.search.lastOpts = opts;
    state.search.solutions = [];
    state.search.cursor = 0;
    state.search.running = true;
    state.search.lastProgress = null;
    renderSearchTable();
    renderSearchNav();
    setSearchButtons(true);
    document.getElementById('searchResults').style.display = '';
    document.getElementById('searchResultsTableWrap').innerHTML = '';
    setProgressBar(0);
    updateCounters({ candidates: 0, coveredCount: 0, exitPass: 0, parityPass: 0, reflPass: 0, afterDedup: 0, footprintsTried: 0, footprintsTotal: 0 });

    if (!state.search.worker) {
      try {
        state.search.worker = new Worker(buildWorkerBlobUrl());
        state.search.worker.onmessage = onWorkerMessage;
        state.search.worker.onerror = e => {
          console.error('Worker error:', e);
          alert('Search worker error: ' + (e.message || e));
          stopSearch(true);
        };
      } catch (err) {
        alert('Failed to start Worker: ' + err.message);
        state.search.running = false;
        setSearchButtons(false);
        return;
      }
    }
    state.search.worker.postMessage({ type: 'run', opts });
  }

  function stopSearch(force = false) {
    if (!state.search.running && !force) return;
    if (state.search.worker) state.search.worker.postMessage({ type: 'cancel' });
    state.search.running = false;
    setSearchButtons(false);
  }

  function onWorkerMessage(ev) {
    const { type, payload } = ev.data;
    if (type === 'progress') {
      state.search.lastProgress = payload;
      updateCounters(payload);
    } else if (type === 'solution') {
      state.search.solutions.push(payload);
      const list = filteredSolutions();
      if (list.length === 1) stepTo(0);   // auto-load the first matching result
      else { renderSearchTable(); renderSearchNav(); }
    } else if (type === 'done') {
      state.search.running = false;
      setSearchButtons(false);
      setProgressBar(1);
      updateCounters({
        candidates: payload.candidates,
        coveredCount: payload.coveredCount,
        exitPass: payload.exitPass,
        parityPass: payload.parityPass,
        reflPass: payload.reflPass,
        afterDedup: payload.afterDedup,
        twistPass: payload.twistPass,
        footprintsTried: payload.footprintsTried,
        footprintsTotal: payload.footprintsTotal,
      });
      renderSearchTable();
      renderSearchNav();
    } else if (type === 'error') {
      alert('Search rejected: ' + payload);
      state.search.running = false;
      setSearchButtons(false);
    }
  }

  function setSearchButtons(running) {
    document.getElementById('searchRunBtn').disabled = running;
    document.getElementById('searchStopBtn').disabled = !running;
    const hasSols = state.search.solutions.length > 0;
    document.getElementById('searchExportCsv').disabled = !hasSols;
    document.getElementById('searchExportJson').disabled = !hasSols;
  }

  function setProgressBar(fraction) {
    document.getElementById('searchProgress').style.width = `${Math.min(100, Math.max(0, fraction * 100))}%`;
  }

  function updateCounters(p) {
    if (p.footprintsTotal > 0) setProgressBar(p.footprintsTried / p.footprintsTotal);
    document.getElementById('searchCounters').innerHTML = `
      Footprints: ${p.footprintsTried ?? 0} / ${p.footprintsTotal ?? 0}<br>
      Candidates: ${(p.candidates ?? 0).toLocaleString()}<br>
      Covered: ${(p.coveredCount ?? 0).toLocaleString()}<br>
      Exit shape: ${p.exitPass ?? 0}<br>
      Parity: ${p.parityPass ?? 0}<br>
      Reflection: ${p.reflPass ?? 0}<br>
      After dedup: ${p.afterDedup ?? 0}<br>
      Twist=0: ${p.twistPass ?? 0}
    `;
  }

  // --- Result browsing (filter + prev/next stepper) ---
  function filteredSolutions() {
    let list = state.search.solutions;
    if (state.search.stacks === 2) {
      // 2-stack: 3-stack filters don't apply; reuse the "Tw=0 only" checkbox as "foldable only".
      return state.search.tw0Only ? list.filter(s => s.verdict.foldable) : list;
    }
    if (state.search.decompFilter) list = list.filter(s => s.decomposition === state.search.decompFilter);
    if (state.search.shapeFilter) list = list.filter(s => s.footprint.shape === state.search.shapeFilter);
    if (state.search.tw0Only) list = list.filter(s => s.verdict.twist);
    // Findings-join filters (no-op when their control is ''): physical result, engine-predicted, custom tags.
    if (state.search.actualFilter) {
      list = list.filter(s => {
        const f = findingFor(s);
        const a = !f || f.foldable === null || f.foldable === undefined
          ? 'untested' : (f.foldable ? 'fold' : 'jam');
        return a === state.search.actualFilter;
      });
    }
    if (state.search.predFilter) {
      const want = state.search.predFilter === 'yes';
      list = list.filter(s => predictedFoldable(s) === want);
    }
    for (const [key, want] of Object.entries(state.search.tagFilters)) {
      if (want === '' || want === undefined) continue;
      const wantBool = want === true || want === 'true';
      list = list.filter(s => { const f = findingFor(s); return f && f.tags && f.tags[key] === wantBool; });
    }
    return list;
  }

  function anyFindingFilterActive() {
    return !!state.search.actualFilter || !!state.search.predFilter
      || Object.values(state.search.tagFilters).some(v => v !== '' && v !== undefined);
  }

  function renderSearchNav() {
    const nav = document.getElementById('searchNav');
    const list = filteredSolutions();
    const total = state.search.solutions.length;
    if (total === 0) { nav.style.display = 'none'; return; }
    nav.style.display = '';
    if (state.search.cursor >= list.length) state.search.cursor = Math.max(0, list.length - 1);
    const cur = list[state.search.cursor];
    document.getElementById('searchNavCounter').textContent =
      list.length ? `Result ${state.search.cursor + 1} of ${list.length}` : 'Result 0 of 0';
    document.getElementById('searchNavSummary').textContent = !cur ? ''
      : state.search.stacks === 2
        ? `HC #${cur.id}  ${cur.verdict.foldable ? '✓ foldable' : '✗ not foldable'}  (Tw=${cur.twistValue})`
        : `Tw=0 ${cur.verdict.twist ? '✓' : '✗'}  ${cur.footprint.shape} ${cur.decomposition}`;
    const filtered = state.search.tw0Only || state.search.decompFilter || state.search.shapeFilter
      || anyFindingFilterActive();
    document.getElementById('searchNavShowing').textContent =
      filtered ? `showing ${list.length} of ${total}` : '';
    document.getElementById('searchPrevBtn').disabled = state.search.cursor <= 0 || !list.length;
    document.getElementById('searchNextBtn').disabled = state.search.cursor >= list.length - 1 || !list.length;
  }

  function stepTo(idx) {
    const list = filteredSolutions();
    if (!list.length) { renderSearchNav(); return; }
    state.search.cursor = Math.max(0, Math.min(list.length - 1, idx));
    const sol = list[state.search.cursor];
    if (state.search.stacks === 2) loadTwoStack(sol);
    else api.loadSolution(sol.id);
    renderSearchNav();
    renderSearchTable();
    updateFindingPanel();
  }

  // Programmatic load of a results payload ({meta,solutions} or bare array). Shared by the
  // file picker and by automation (screenshots). Returns the solution count.
  function loadResultsData(data) {
    const sols = Array.isArray(data) ? data : data.solutions;
    if (!Array.isArray(sols)) throw new Error('no "solutions" array');
    for (const s of sols) { if (s && s.canonicalHash) s._normHash = normHash(s.canonicalHash); }
    state.search.solutions = sols;
    state.search.lastOpts = (data.meta && data.meta.opts) || state.search.lastOpts || {};
    state.search.stacks = (data.meta && data.meta.stacks) || 3;
    state.search.cursor = 0;
    if (data.meta && data.meta.m && data.meta.n) {
      state.search.dims = { m: data.meta.m, n: data.meta.n };
      document.getElementById('searchM').value = data.meta.m;
      document.getElementById('searchN').value = data.meta.n;
    }
    document.getElementById('searchResults').style.display = '';
    setSearchButtons(false);
    renderSearchTable();
    if (filteredSolutions().length) stepTo(0); else renderSearchNav();
    return sols.length;
  }

  // 2-stack: render an HC pattern onto the focused grid (no group rebuild).
  function loadTwoStack(sol) {
    const gridId = state.focusedGridId;
    const g = state.grids.find(x => x.id === gridId);
    if (!g) return;
    const d = state.search.dims;
    if (d) { g.m = d.m; g.n = d.n; }
    g.cells.clear(); g.footprint.clear(); g.groups = [];
    state.activeGroupId = null;
    refreshGroupSelect();
    const view = state.views.get(gridId);
    view.twoStack = sol;
    document.getElementById('mInput').value = g.m;
    document.getElementById('nInput').value = g.n;
    view.render();
  }

  // Jump to a solution by its id (clears filters if they hide it). For automation.
  function stepToId(id) {
    let idx = filteredSolutions().findIndex(s => s.id === id);
    if (idx < 0) {
      state.search.tw0Only = false;
      state.search.decompFilter = '';
      state.search.shapeFilter = '';
      clearFindingFilters();
      const tw = document.getElementById('searchTw0Only');
      const df = document.getElementById('searchDecompFilter');
      const sf = document.getElementById('searchShapeFilter');
      if (tw) tw.checked = false;
      if (df) df.value = '';
      if (sf) sf.value = '';
      renderSearchTable();
      idx = filteredSolutions().findIndex(s => s.id === id);
    }
    if (idx < 0) return false;
    stepTo(idx);
    return true;
  }

  function renderSearchTable() {
    const wrap = document.getElementById('searchResultsTableWrap');
    const cnt = document.getElementById('searchResultsCount');
    const list = filteredSolutions();
    cnt.textContent = state.search.tw0Only
      ? `(${list.length} of ${state.search.solutions.length})`
      : `(${state.search.solutions.length})`;
    if (!list.length) { wrap.innerHTML = '<p class="hint" style="padding:8px">No solutions yet.</p>'; return; }

    if (state.search.stacks === 2) {
      const head = `<thead><tr><th>#</th><th>Reflection</th><th>Twist</th><th>Foldable</th><th>Tw</th><th></th></tr></thead>`;
      const rows = list.map((s, i) => {
        const pf = ok => ok ? '<td class="verdict-pass">✓</td>' : '<td class="verdict-fail">✗</td>';
        return `<tr class="${i === state.search.cursor ? 'current-sol' : ''}" data-idx="${i}">
          <td>${s.id}</td>${pf(s.verdict.reflection)}${pf(s.verdict.twist)}${pf(s.verdict.foldable)}
          <td>${s.twistValue}</td>
          <td><button class="load-sol" data-idx="${i}">► Show</button></td></tr>`;
      }).join('');
      wrap.innerHTML = `<table class="search-results">${head}<tbody>${rows}</tbody></table>`;
      wrap.querySelectorAll('button.load-sol').forEach(btn =>
        btn.addEventListener('click', () => stepTo(+btn.dataset.idx)));
      return;
    }
    const head = `
      <thead><tr>
        <th>#</th><th>Shape</th><th>Rot</th><th>Anchor</th><th>Decomp</th>
        <th>Chain kinds</th><th>N_H</th><th>N_V</th><th>Exit</th><th>Parity</th><th>Refl</th><th>Twist</th><th>Fold</th><th></th>
      </tr></thead>
    `;
    const rows = list.map((s, i) => {
      const kinds = s.chains.map(c => c.kind === '2chain' ? '2c' : '1c').join(',');
      const nH = s.chains.map(c => c.nH).join(';');
      const nV = s.chains.map(c => c.nV).join(';');
      const par = s.verdict.parity ? '<td class="verdict-pass">✓</td>' : '<td class="verdict-fail">✗</td>';
      const ref = s.verdict.reflection ? '<td class="verdict-pass">✓</td>' : '<td class="verdict-fail">✗</td>';
      const ext = s.verdict.exitFootprint ? '<td class="verdict-pass">✓</td>' : '<td class="verdict-fail">✗</td>';
      const twTitle = (s.twistPairs || []).map(p => `${p.i}-${p.j}:${p.tw}`).join(' ');
      const tw = s.verdict.twist === null
        ? `<td class="verdict-stub" title="2-chain twist not yet supported">—</td>`
        : s.verdict.twist
          ? `<td class="verdict-pass" title="pair twist ${twTitle}">✓</td>`
          : `<td class="verdict-fail" title="pair twist ${twTitle}">✗</td>`;
      const fold = foldCell(findingFor(s));
      return `<tr class="${i === state.search.cursor ? 'current-sol' : ''}" data-idx="${i}">
        <td>${s.id}</td>
        <td>${s.footprint.shape}</td>
        <td>${s.footprint.rotation}</td>
        <td>(${s.footprint.anchor.x},${s.footprint.anchor.y})</td>
        <td>${s.decomposition}</td>
        <td>${kinds}</td>
        <td>${nH}</td>
        <td>${nV}</td>
        ${ext}${par}${ref}
        ${tw}
        ${fold}
        <td><button class="load-sol" data-idx="${i}">► Load</button></td>
      </tr>`;
    }).join('');
    wrap.innerHTML = `<table class="search-results">${head}<tbody>${rows}</tbody></table>`;
    wrap.querySelectorAll('button.load-sol').forEach(btn => {
      btn.addEventListener('click', () => stepTo(+btn.dataset.idx));
    });
  }

  function escapeCsv(v) {
    const s = String(v);
    if (s.includes(',') || s.includes('"') || s.includes(';')) return `"${s.replace(/"/g, '""')}"`;
    return s;
  }

  function exportCsv() {
    const opts = state.search.lastOpts || {};
    const m = opts.m, n = opts.n;
    const header = ['id','m','n','shape','rotation','anchorX','anchorY','decomp','chain_count','nH_list','nV_list','exit_pass','parity_pass','refl_pass','twist','tw_list'];
    const lines = [header.join(',')];
    for (const s of state.search.solutions) {
      const row = [
        s.id, m, n,
        s.footprint.shape, s.footprint.rotation,
        s.footprint.anchor.x, s.footprint.anchor.y,
        s.decomposition,
        s.chains.length,
        s.chains.map(c => c.nH).join(';'),
        s.chains.map(c => c.nV).join(';'),
        s.verdict.exitFootprint, s.verdict.parity, s.verdict.reflection,
        s.verdict.twist === null ? 'pending' : s.verdict.twist,
        (s.twistPairs || []).map(p => `${p.i}-${p.j}:${p.tw}`).join(';'),
      ].map(escapeCsv);
      lines.push(row.join(','));
    }
    download(`search-${m}x${n}.csv`, lines.join('\n'), 'text/csv');
  }

  function exportJson() {
    const opts = state.search.lastOpts || {};
    const payload = {
      meta: { m: opts.m, n: opts.n, opts, generated: new Date().toISOString() },
      solutions: state.search.solutions,
    };
    download(`search-${opts.m}x${opts.n}.json`, JSON.stringify(payload, null, 2), 'application/json');
  }

  function download(name, text, mime) {
    const blob = new Blob([text], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = name; document.body.appendChild(a); a.click();
    setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 0);
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  // --- Findings join (results/foldfindings.json) -------------------------------------------------
  // Findings live in a separate DB keyed by canonicalHash; the browser joins them onto the loaded
  // candidates so they can be filtered/shown by recorded result + custom tags. The DB stores hashes
  // both normalized (submit) and raw (migrated), and sol.canonicalHash is raw — so BOTH sides go
  // through normHash (must match Python findings._norm_hash: deep key-sort + compact separators).
  function sortKeysDeep(v) {
    if (Array.isArray(v)) return v.map(sortKeysDeep);
    if (v && typeof v === 'object') {
      return Object.keys(v).sort().reduce((o, k) => { o[k] = sortKeysDeep(v[k]); return o; }, {});
    }
    return v;
  }
  function normHash(h) {
    try { return JSON.stringify(sortKeysDeep(JSON.parse(h))); } catch { return h; }
  }

  function ingestFindings(arr) {
    const m = new Map();
    for (const f of (Array.isArray(arr) ? arr : [])) {
      if (f && f.canonicalHash) { try { m.set(normHash(f.canonicalHash), f); } catch { /* skip */ } }
    }
    state.findings.byHash = m;
    state.findings.loaded = true;
    rebuildTagFilterControls();
    renderSearchNav();
    renderSearchTable();
    updateFindingPanel();
  }

  async function loadFindings() {
    try {
      const res = await fetch('results/foldfindings.json');
      if (!res.ok) throw new Error(`findings ${res.status}`);
      ingestFindings(await res.json());
    } catch (err) {
      state.findings.loaded = false;     // missing file / file:// -> empty cache, no alert
    }
  }

  function findingFor(sol) {
    if (!sol) return null;
    const key = sol._normHash || normHash(sol.canonicalHash);
    return state.findings.byHash.get(key) || null;
  }

  // Engine "predicted foldable" derived from the candidate's own verdict (every candidate has one),
  // so the filter works even with no recorded finding. null twist (2-chain pending) counts as not-failing.
  function predictedFoldable(sol) {
    const v = sol.verdict || {};
    return !!v.parity && !!v.reflection && v.twist !== false;
  }

  // Table cell for a candidate's recorded physical result (— = no finding, untested/FOLD/JAM otherwise).
  function foldCell(f) {
    if (!f) return '<td class="verdict-stub" title="no recorded finding">—</td>';
    if (f.foldable === null || f.foldable === undefined)
      return '<td class="verdict-stub" title="recorded, result untested">untested</td>';
    return f.foldable
      ? '<td class="verdict-pass" title="physically folds">FOLD</td>'
      : '<td class="verdict-fail" title="physically jams">JAM</td>';
  }

  // Re-run the filter and refresh the table/stepper. Shared by every filter control (search + findings).
  function applyFilterChange() {
    state.search.cursor = 0;
    renderSearchTable();
    if (filteredSolutions().length) stepTo(0); else renderSearchNav();
  }

  // Custom-tag filters are discovered from the loaded findings (union of every finding's tags keys).
  function discoverTagKeys() {
    const keys = new Set();
    for (const f of state.findings.byHash.values()) {
      if (f && f.tags) for (const k of Object.keys(f.tags)) keys.add(k);
    }
    return [...keys].sort();
  }

  // Rebuild the #findingFilters row: static actual/predicted selects stay in markup; this injects one
  // tri-state <select> per discovered tag key (keys are user-authored → HTML-escaped) and prunes stale
  // filter state. The whole row hides for 2-stack results or when no findings are loaded.
  function rebuildTagFilterControls() {
    const row = document.getElementById('findingFilters');
    if (!row) return;
    const show = state.search.stacks === 3 && state.findings.byHash.size > 0;
    row.style.display = show ? '' : 'none';
    if (!show) return;
    const keys = discoverTagKeys();
    // Drop filter state for keys that no longer exist.
    for (const k of Object.keys(state.search.tagFilters)) {
      if (!keys.includes(k)) delete state.search.tagFilters[k];
    }
    const box = document.getElementById('tagFilterControls');
    if (!box) return;
    box.innerHTML = keys.map(k => {
      const ek = escapeHtml(k), cur = state.search.tagFilters[k] || '';
      const opt = (v, lbl) => `<option value="${v}"${cur === v ? ' selected' : ''}>${lbl}</option>`;
      return `<label class="opt mono">${ek}
        <select class="tag-filter" data-key="${escapeAttr(k)}">
          ${opt('', 'any')}${opt('true', 'true')}${opt('false', 'false')}
        </select></label>`;
    }).join('');
    box.querySelectorAll('select.tag-filter').forEach(sel => {
      sel.addEventListener('change', () => {
        state.search.tagFilters[sel.dataset.key] = sel.value;
        applyFilterChange();
      });
    });
  }

  function escapeAttr(s) { return escapeHtml(s).replace(/`/g, '&#96;'); }

  // Reset all findings-join filters (state + DOM). Called by Clear and by stepToId's filter-clear.
  function clearFindingFilters() {
    state.search.actualFilter = '';
    state.search.predFilter = '';
    state.search.tagFilters = {};
    const fa = document.getElementById('filterActual');
    const fp = document.getElementById('filterPredicted');
    if (fa) fa.value = '';
    if (fp) fp.value = '';
    rebuildTagFilterControls();
  }

  // --- Physical-finding capture (record a paper-fold result against a candidate's canonicalHash) ---
  // The page never runs the engine: it assembles a FoldFinding from the loaded solution + the form
  // and hands it to the backend (serve.py POST) or downloads it (CLI `findings.py submit` fallback).
  // `predicted` is filled server-side, never here.
  function currentSolution() {
    if (state.search.stacks !== 3) return null;            // findings target 3-stack candidates only
    const list = filteredSolutions();
    return list[state.search.cursor] || null;
  }

  function findingDims() {
    const m = (state.search.dims && state.search.dims.m) || +document.getElementById('searchM').value;
    const n = (state.search.dims && state.search.dims.n) || +document.getElementById('searchN').value;
    return { m, n };
  }

  // Preset tag keys (persisted once) drive the per-finding toggles, so filters stay typo-consistent.
  const TAG_KEYS_LS = 'foldfinding.tagKeys';
  function getTagKeys() {
    let raw = '';
    try { raw = localStorage.getItem(TAG_KEYS_LS) || ''; } catch { /* private mode */ }
    return raw.split(',').map(s => s.trim()).filter(Boolean);
  }
  function saveTagKeys(csv) {
    const keys = csv.split(',').map(s => s.trim()).filter(Boolean);
    try { localStorage.setItem(TAG_KEYS_LS, keys.join(',')); } catch { /* private mode */ }
    return keys;
  }

  // One label + tri-radio (true/false/untested, default untested) per configured key. `prefill` (a
  // finding's tags) sets the initial value when re-opening a candidate that already has a finding.
  function renderTagRows(prefill) {
    const box = document.getElementById('findingTagRows');
    if (!box) return;
    const keys = getTagKeys();
    if (!keys.length) { box.innerHTML = '<span class="hint">no tag keys set</span>'; return; }
    box.innerHTML = keys.map((k, i) => {
      const ek = escapeHtml(k), ak = escapeAttr(k), nm = `tag-${i}`;   // index name = safe radio grouping
      const want = prefill && Object.prototype.hasOwnProperty.call(prefill, k) ? prefill[k] : undefined;
      const sel = v => (v === 'true' ? want === true : v === 'false' ? want === false : want === undefined) ? ' checked' : '';
      const r = v => `<label><input type="radio" name="${nm}" data-tagkey="${ak}" value="${v}"${sel(v)}> ${v}</label>`;
      return `<div class="tag-row"><span class="mono">${ek}</span>${r('true')}${r('false')}${r('untested')}</div>`;
    }).join('');
  }

  // Collect the checked per-key radios into a tags map by data-tagkey (no selector-escaping of user keys);
  // untested keys are OMITTED (lean records; absent ⇒ untested).
  function readTagsFromPanel() {
    const tags = {};
    const wanted = new Set(getTagKeys());
    document.querySelectorAll('#findingTagRows input[type=radio]:checked').forEach(el => {
      const k = el.dataset.tagkey;
      if (!wanted.has(k)) return;
      if (el.value === 'true') tags[k] = true;
      else if (el.value === 'false') tags[k] = false;
    });
    return tags;
  }

  function buildFinding() {
    const sol = currentSolution();
    if (!sol) return null;
    const { m, n } = findingDims();
    const v = (document.querySelector('input[name=findingFoldable]:checked') || {}).value || 'untested';
    const foldable = v === 'untested' ? null : v === 'fold';
    const rec = {
      grid: `${m}x${n}`,
      id: sol.id,
      canonicalHash: sol.canonicalHash,
      foldable,
      foldOrder: (sol.chains || []).flatMap(c => c.foldArrows || []),   // provenance only, never matched
      by: (document.getElementById('findingBy').value || '').trim() || 'anon',
      date: new Date().toISOString().slice(0, 10),
      notes: (document.getElementById('findingNotes').value || '').trim(),
    };
    if (foldable === false) {                                // jam detail only when the fold jammed
      const af = document.getElementById('findingAtFold').value;
      const reason = document.getElementById('findingReason').value;
      rec.jam = { atFold: af === '' ? null : parseInt(af, 10), crease: null, reason: reason || null };
    }
    const tags = readTagsFromPanel();
    if (Object.keys(tags).length) rec.tags = tags;
    return rec;
  }

  function setFindingStatus(msg, ok) {
    const el = document.getElementById('findingStatus');
    if (el) { el.textContent = msg; el.style.color = ok === false ? '#c33' : (ok ? '#161' : '#888'); }
  }

  // Reflect the loaded candidate into the capture panel (surface the exact canonicalHash the DB keys on).
  function updateFindingPanel() {
    const hashEl = document.getElementById('findingHash');
    if (!hashEl) return;
    const sol = currentSolution();
    const identEl = document.getElementById('findingIdent');
    const recBtn = document.getElementById('recordFindingBtn');
    const subBtn = document.getElementById('submitFindingBtn');
    if (!sol) {
      hashEl.value = ''; identEl.textContent = '(load a 3-stack candidate)';
      recBtn.disabled = true; subBtn.disabled = true;
      renderTagRows(null);
      return;
    }
    const { m, n } = findingDims();
    hashEl.value = sol.canonicalHash || '';
    identEl.textContent = `${m}x${n} #${sol.id}  ${(sol.footprint && sol.footprint.shape) || ''} ${sol.decomposition || ''}`;
    recBtn.disabled = false; subBtn.disabled = false;
    const f = findingFor(sol);                       // re-submit upserts on hash → prefill so tags aren't erased
    renderTagRows(f && f.tags ? f.tags : null);
  }

  function exportFinding() {
    const rec = buildFinding();
    if (!rec) return;
    download(`finding-${rec.grid}-${rec.id}.json`, JSON.stringify(rec, null, 2), 'application/json');
    setFindingStatus(`downloaded finding-${rec.grid}-${rec.id}.json — submit via: python py/findings.py submit <file>`);
  }

  async function submitFinding() {
    const rec = buildFinding();
    if (!rec) return;
    setFindingStatus('submitting…');
    try {
      const res = await fetch('/api/findings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(rec),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok && data.ok) {
        const p = data.record && data.record.predicted;
        const eng = p ? (p.matched ? (p.foldable ? 'FOLD' : 'JAM') : 'no engine match') : 'n/a';
        await loadFindings();    // refresh the join so the new result/tags show in table + filters
        setFindingStatus(`saved ${rec.grid}#${rec.id} (engine predicted: ${eng})`, true);
      } else {
        setFindingStatus(`rejected: ${data.error || res.status} — downloading instead`, false);
        exportFinding();
      }
    } catch (err) {
      setFindingStatus(`no POST server (run serve.py) — downloading instead: ${err.message}`, false);
      exportFinding();
    }
  }

  function wireFindingPanel() {
    const recBtn = document.getElementById('recordFindingBtn');
    const subBtn = document.getElementById('submitFindingBtn');
    if (recBtn) recBtn.addEventListener('click', exportFinding);
    if (subBtn) subBtn.addEventListener('click', submitFinding);
    const keyInput = document.getElementById('findingTagKeys');
    const keySave = document.getElementById('findingTagKeysSave');
    if (keyInput) keyInput.value = getTagKeys().join(', ');
    if (keySave) keySave.addEventListener('click', () => {
      const keys = saveTagKeys(keyInput ? keyInput.value : '');
      if (keyInput) keyInput.value = keys.join(', ');
      renderTagRows(null);
    });
    updateFindingPanel();
  }

  function wireSearchPanel() {
    document.getElementById('searchRunBtn').addEventListener('click', startSearch);
    document.getElementById('searchStopBtn').addEventListener('click', () => stopSearch());
    document.getElementById('searchExportCsv').addEventListener('click', exportCsv);
    document.getElementById('searchExportJson').addEventListener('click', exportJson);
    document.getElementById('searchClearBtn').addEventListener('click', () => {
      state.search.solutions = [];
      state.search.cursor = 0;
      state.search.tw0Only = false;
      state.search.decompFilter = '';
      state.search.shapeFilter = '';
      clearFindingFilters();
      document.getElementById('searchTw0Only').checked = false;
      document.getElementById('searchDecompFilter').value = '';
      document.getElementById('searchShapeFilter').value = '';
      document.getElementById('searchResults').style.display = 'none';
      document.getElementById('searchResultsTableWrap').innerHTML = '';
      document.getElementById('searchCounters').innerHTML = '';
      setProgressBar(0);
      setSearchButtons(false);
      renderSearchNav();
      updateFindingPanel();
    });

    // Load precomputed results JSON (from Python generate.py, or a prior browser export)
    document.getElementById('searchLoadJson').addEventListener('change', e => {
      const file = e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => {
        try {
          loadResultsData(JSON.parse(reader.result));
        } catch (err) {
          alert('Could not load results JSON: ' + err.message);
        }
        e.target.value = '';
      };
      reader.readAsText(file);
    });

    // Result browsing
    document.getElementById('searchPrevBtn').addEventListener('click', () => stepTo(state.search.cursor - 1));
    document.getElementById('searchNextBtn').addEventListener('click', () => stepTo(state.search.cursor + 1));
    document.getElementById('searchTw0Only').addEventListener('change', e => {
      state.search.tw0Only = e.target.checked; applyFilterChange();
    });
    document.getElementById('searchDecompFilter').addEventListener('change', e => {
      state.search.decompFilter = e.target.value; applyFilterChange();
    });
    document.getElementById('searchShapeFilter').addEventListener('change', e => {
      state.search.shapeFilter = e.target.value; applyFilterChange();
    });
    const fa = document.getElementById('filterActual');
    if (fa) fa.addEventListener('change', e => { state.search.actualFilter = e.target.value; applyFilterChange(); });
    const fp = document.getElementById('filterPredicted');
    if (fp) fp.addEventListener('change', e => { state.search.predFilter = e.target.value; applyFilterChange(); });
    document.addEventListener('keydown', e => {
      const tag = (document.activeElement?.tagName) || '';
      if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return;
      if (!state.search.solutions.length) return;
      if (e.key === 'ArrowLeft') { stepTo(state.search.cursor - 1); e.preventDefault(); }
      else if (e.key === 'ArrowRight') { stepTo(state.search.cursor + 1); e.preventDefault(); }
    });
  }

  return { init, loadResultsData, stepToId, setMode,
           solutionCount: () => state.search.solutions.length };
})();

window.App = App;   // expose for automation (Playwright screenshots) and console use
window.addEventListener('DOMContentLoaded', App.init);
