// grid.js — GridView class. Renders one grid card; handles pointer events per tool.

const CELL = 32;          // px per cell
const SVG_NS = 'http://www.w3.org/2000/svg';
const key = (x, y) => `${x},${y}`;

class GridView {
  constructor(state, app) {
    this.state = state;       // GridState (mutated in place)
    this.app = app;           // back-ref for tool / color / activeGroup
    this.root = document.createElement('div');
    this.root.className = 'grid-card';
    this.root.tabIndex = 0;
    this.root.addEventListener('pointerdown', () => app.focusGrid(state.id), true);
    this.dragState = null;    // tool-specific transient state during a drag
    this.twoStack = null;     // when set, render() draws a 2-stack HC pattern instead
    this.build();
  }

  // --- DOM scaffold ---
  build() {
    this.root.innerHTML = '';
    const header = document.createElement('div');
    header.className = 'card-header';
    header.innerHTML = `
      <span class="title">${this.state.label}</span>
      <span>m=${this.state.m} n=${this.state.n}</span>
      <span class="spacer"></span>
      <button data-act="addGroup">+ Group</button>
      <button data-act="resetFolds">Reset folds</button>
      <button data-act="clearVectors">Clear vectors</button>
      <button data-act="clearAll">Clear</button>
      <button data-act="delete">×</button>
    `;
    header.addEventListener('click', e => {
      const act = e.target.dataset?.act;
      if (!act) return;
      if (act === 'addGroup') this.app.addGroup(this.state.id);
      if (act === 'resetFolds') this.app.resetFolds(this.state.id);
      if (act === 'clearVectors') this.app.clearVectors(this.state.id);
      if (act === 'clearAll') this.app.clearAll(this.state.id);
      if (act === 'delete') this.app.deleteGrid(this.state.id);
    });
    this.root.appendChild(header);

    const wrap = document.createElement('div');
    wrap.className = 'svg-wrap';
    this.svg = document.createElementNS(SVG_NS, 'svg');
    this.svg.classList.add('grid');
    this.svg.addEventListener('pointerdown', e => this.onPointerDown(e));
    this.svg.addEventListener('pointermove', e => this.onPointerMove(e));
    this.svg.addEventListener('pointerup', e => this.onPointerUp(e));
    this.svg.addEventListener('pointercancel', e => this.onPointerUp(e));
    this.svg.addEventListener('contextmenu', e => e.preventDefault());
    wrap.appendChild(this.svg);
    this.root.appendChild(wrap);

    this.counters = document.createElement('div');
    this.counters.className = 'group-counters';
    this.root.appendChild(this.counters);
  }

  setFocused(focused) {
    this.root.classList.toggle('focused', focused);
  }

  // --- Coord helpers ---
  cellFromEvent(e) {
    const rect = this.svg.getBoundingClientRect();
    const x = Math.floor((e.clientX - rect.left) / CELL);
    const y = Math.floor((e.clientY - rect.top) / CELL);
    return { x, y };
  }
  inGrid(c) {
    return c.x >= 0 && c.x < this.state.m && c.y >= 0 && c.y < this.state.n;
  }
  pxCenter(x, y) { return { cx: x * CELL + CELL / 2, cy: y * CELL + CELL / 2 }; }

  // Cell-side normal: unit vector pointing from the crease INTO the cell that owns the vector.
  static cellNormal(edge) {
    if (edge === 'T') return { x: 0, y: 1 };
    if (edge === 'B') return { x: 0, y: -1 };
    if (edge === 'L') return { x: 1, y: 0 };
    return { x: -1, y: 0 };   // R
  }

  // Half-arrow: main line + one barb on the cellNormal side.
  drawHalfArrow(x1, y1, x2, y2, color, cellNormal, headSize = 8, strokeW = 2) {
    const len = Math.hypot(x2 - x1, y2 - y1) || 1;
    const ux = (x2 - x1) / len, uy = (y2 - y1) / len;
    const baseX = x2 - ux * headSize;
    const baseY = y2 - uy * headSize;
    const bx = baseX + cellNormal.x * headSize * 0.7;
    const by = baseY + cellNormal.y * headSize * 0.7;

    const line = document.createElementNS(SVG_NS, 'line');
    line.setAttribute('class', 'vector');
    line.setAttribute('x1', x1); line.setAttribute('y1', y1);
    line.setAttribute('x2', x2); line.setAttribute('y2', y2);
    line.setAttribute('stroke', color); line.setAttribute('stroke-width', strokeW);
    line.setAttribute('stroke-linecap', 'round');
    this.svg.appendChild(line);

    const barb = document.createElementNS(SVG_NS, 'line');
    barb.setAttribute('class', 'vector');
    barb.setAttribute('x1', x2); barb.setAttribute('y1', y2);
    barb.setAttribute('x2', bx); barb.setAttribute('y2', by);
    barb.setAttribute('stroke', color); barb.setAttribute('stroke-width', strokeW);
    barb.setAttribute('stroke-linecap', 'round');
    this.svg.appendChild(barb);
  }

  // Full symmetric arrow (used for fold-direction chevron only).
  drawFullArrow(x1, y1, x2, y2, color, headSize = 8, strokeW = 2) {
    const len = Math.hypot(x2 - x1, y2 - y1) || 1;
    const ux = (x2 - x1) / len, uy = (y2 - y1) / len;
    const px = -uy, py = ux;
    const baseX = x2 - ux * headSize;
    const baseY = y2 - uy * headSize;
    const lx = baseX + px * headSize * 0.5, ly = baseY + py * headSize * 0.5;
    const rx = baseX - px * headSize * 0.5, ry = baseY - py * headSize * 0.5;

    const line = document.createElementNS(SVG_NS, 'line');
    line.setAttribute('class', 'fold-arrow');
    line.setAttribute('x1', x1); line.setAttribute('y1', y1);
    line.setAttribute('x2', baseX); line.setAttribute('y2', baseY);
    line.setAttribute('stroke', color); line.setAttribute('stroke-width', strokeW);
    line.setAttribute('stroke-linecap', 'round');
    this.svg.appendChild(line);

    const head = document.createElementNS(SVG_NS, 'polygon');
    head.setAttribute('class', 'head');
    head.setAttribute('points', `${x2},${y2} ${lx},${ly} ${rx},${ry}`);
    head.setAttribute('fill', color);
    this.svg.appendChild(head);
  }

  // Given a vector { x, y, edge, sign }, render a half-arrow lying ALONG that cell's edge.
  drawEdgeVector(v, color) {
    const sizePx = Math.max(4, this.app.display.vectorSize | 0);
    const halfLen = Math.min(CELL * 0.45, sizePx);   // line half-length, anchored at edge midpoint
    const mx = v.x * CELL + CELL / 2;
    const my = v.y * CELL + CELL / 2;
    let a, b;   // endpoints along the edge (a = sign +1 tail, b = sign +1 head)
    if (v.edge === 'T') { a = { x: mx - halfLen, y: v.y * CELL }; b = { x: mx + halfLen, y: v.y * CELL }; }
    else if (v.edge === 'B') { a = { x: mx - halfLen, y: (v.y + 1) * CELL }; b = { x: mx + halfLen, y: (v.y + 1) * CELL }; }
    else if (v.edge === 'L') { a = { x: v.x * CELL, y: my - halfLen }; b = { x: v.x * CELL, y: my + halfLen }; }
    else /* R */ { a = { x: (v.x + 1) * CELL, y: my - halfLen }; b = { x: (v.x + 1) * CELL, y: my + halfLen }; }
    const [tail, head] = v.sign >= 0 ? [a, b] : [b, a];
    const cellN = GridView.cellNormal(v.edge);
    const headSize = Math.max(5, sizePx * 0.55);
    this.drawHalfArrow(tail.x, tail.y, head.x, head.y, color, cellN, headSize, 2.5);
  }

  // Given a pointer event inside a cell, derive {edge, sign} by drag offset and direction.
  snapVectorFromDrag(anchor, startPx, endPx) {
    const dx = endPx.x - startPx.x, dy = endPx.y - startPx.y;
    if (Math.hypot(dx, dy) < 4) return null;
    const startInCellX = startPx.x - anchor.x * CELL;
    const startInCellY = startPx.y - anchor.y * CELL;
    if (Math.abs(dx) >= Math.abs(dy)) {
      const edge = startInCellY < CELL / 2 ? 'T' : 'B';
      const sign = dx >= 0 ? 1 : -1;
      return { x: anchor.x, y: anchor.y, edge, sign };
    } else {
      const edge = startInCellX < CELL / 2 ? 'L' : 'R';
      const sign = dy >= 0 ? 1 : -1;
      return { x: anchor.x, y: anchor.y, edge, sign };
    }
  }

  // --- Render ---
  render() {
    const { m, n } = this.state;
    this.svg.setAttribute('width', m * CELL);
    this.svg.setAttribute('height', n * CELL);
    this.svg.setAttribute('viewBox', `0 0 ${m * CELL} ${n * CELL}`);
    while (this.svg.firstChild) this.svg.removeChild(this.svg.firstChild);

    if (this.twoStack) { this.drawTwoStack(); this.renderHeader(); this.counters.innerHTML = ''; return; }

    const disp = this.app.display;
    const inset = Math.max(0, Math.min(CELL / 2 - 1, disp.placementInset));

    // 1. base cells (always set fill inline so CSS won't override)
    for (let y = 0; y < n; y++) {
      for (let x = 0; x < m; x++) {
        const r = document.createElementNS(SVG_NS, 'rect');
        r.setAttribute('class', 'cell');
        r.setAttribute('x', x * CELL); r.setAttribute('y', y * CELL);
        r.setAttribute('width', CELL); r.setAttribute('height', CELL);
        const cell = this.state.cells.get(key(x, y));
        const paintFill = disp.showPaint ? (cell?.color || '#fff') : '#fff';
        r.setAttribute('fill', paintFill);
        this.svg.appendChild(r);
      }
    }

    // 2. highlights
    if (disp.showPaint) {
      for (const [k, cell] of this.state.cells) {
        if (!cell.highlight) continue;
        const [x, y] = k.split(',').map(Number);
        const r = document.createElementNS(SVG_NS, 'rect');
        r.setAttribute('class', 'highlight');
        r.setAttribute('x', x * CELL); r.setAttribute('y', y * CELL);
        r.setAttribute('width', CELL); r.setAttribute('height', CELL);
        r.setAttribute('fill', cell.highlight);
        this.svg.appendChild(r);
      }
    }

    // 3. footprint outline
    if (disp.showFootprint) {
      for (const k of this.state.footprint) {
        const [x, y] = k.split(',').map(Number);
        const r = document.createElementNS(SVG_NS, 'rect');
        r.setAttribute('class', 'footprint');
        r.setAttribute('x', x * CELL + 1); r.setAttribute('y', y * CELL + 1);
        r.setAttribute('width', CELL - 2); r.setAttribute('height', CELL - 2);
        this.svg.appendChild(r);
      }
    }

    // 4. group placements
    for (const g of this.state.groups) {
      for (let i = 0; i < g.placements.length; i++) {
        const p = g.placements[i];
        const opacity = i === 0 ? 0.55 : 0.4;
        // Always render the base placement (i=0) so groups stay visible; gate only folds.
        if (disp.showPlacements || i === 0) {
          for (const c of p.cells) {
            const r = document.createElementNS(SVG_NS, 'rect');
            r.setAttribute('class', 'placement');
            r.setAttribute('x', c.x * CELL + inset); r.setAttribute('y', c.y * CELL + inset);
            r.setAttribute('width', CELL - 2 * inset); r.setAttribute('height', CELL - 2 * inset);
            r.setAttribute('fill', g.color);
            r.setAttribute('opacity', opacity);
            this.svg.appendChild(r);
          }
        }
        if (disp.showLabels && i === 0 && p.cells.length) {
          const t = document.createElementNS(SVG_NS, 'text');
          const c = p.cells[0];
          t.setAttribute('x', c.x * CELL + 4);
          t.setAttribute('y', c.y * CELL + 12);
          t.setAttribute('font-size', '10');
          t.setAttribute('font-family', 'ui-monospace, Menlo, monospace');
          t.setAttribute('fill', '#222');
          t.textContent = g.label;
          this.svg.appendChild(t);
        }
      }
    }

    // 5. fold-direction chevrons (orange, inline two-sided arrowhead)
    const chev = Math.max(6, disp.chevronSize);
    if (disp.showFoldArrows) for (const g of this.state.groups) {
      for (let i = 1; i < g.placements.length; i++) {
        const p = g.placements[i];
        if (!p.creaseAxis || !p.parentBounds) continue;
        const b = p.parentBounds;
        let x1, y1, x2, y2;
        if (p.creaseAxis === 'h') {
          const xPx = p.creaseAt * CELL;
          const yMid = ((b.yMin + b.yMax + 1) / 2) * CELL;
          const dir = p.foldArrow === 'R' ? 1 : -1;
          x1 = xPx - dir * (chev / 2); x2 = xPx + dir * (chev / 2);
          y1 = y2 = yMid;
        } else {
          const yPx = p.creaseAt * CELL;
          const xMid = ((b.xMin + b.xMax + 1) / 2) * CELL;
          const dir = p.foldArrow === 'D' ? 1 : -1;
          y1 = yPx - dir * (chev / 2); y2 = yPx + dir * (chev / 2);
          x1 = x2 = xMid;
        }
        this.drawFullArrow(x1, y1, x2, y2, '#ff7a18', Math.max(5, chev * 0.4), 2.5);
      }
    }

    // 6. vectors: arrow lying along a cell edge (T/B/L/R), pointing per sign.
    if (disp.showVectors) for (const g of this.state.groups) {
      for (const p of g.placements) {
        for (const v of p.vectors) {
          this.drawEdgeVector(v, g.color);
        }
      }
    }

    // 7. live drag preview (vector-tool drag): show the snapped edge arrow even when vectors hidden
    if (this.dragState?.kind === 'vector' && this.dragState.snapped) {
      this.drawEdgeVector(this.dragState.snapped, this.dragState.color);
    }

    this.renderHeader();
    this.renderCounters();
  }

  renderHeader() {
    const t = this.root.querySelector('.card-header span:nth-child(2)');
    if (t) t.textContent = `m=${this.state.m} n=${this.state.n}`;
  }

  renderCounters() {
    this.counters.innerHTML = '';
    if (!this.state.groups.length) {
      this.counters.innerHTML = '<span style="color:#888;font-size:12px">no groups yet — pick Footprint then Group select tools, then click + Group</span>';
      return;
    }
    for (const g of this.state.groups) {
      const el = document.createElement('span');
      el.className = 'group-counter';
      if (g.id === this.app.activeGroupId) el.classList.add('active');
      el.style.background = g.color;
      el.textContent = `${g.label}  H=${g.hFolds} V=${g.vFolds} T=${g.hFolds + g.vFolds}  (${g.baseCells.length} cells)`;
      el.addEventListener('click', () => this.app.setActiveGroup(g.id));
      this.counters.appendChild(el);
    }
  }

  // --- 2-stack (RSPA Hamiltonian-circuit) rendering ---
  // Draws the kirigami pattern: cells, the HC path, creases (crossed edges, bold red) vs
  // slits (uncrossed interior edges, gray dashed), the cut edge (green), and the verdict.
  drawTwoStack() {
    const { m, n } = this.state;
    const ts = this.twoStack;
    const circ = ts.circuit;
    const N = circ.length;

    const line = (x1, y1, x2, y2, attrs) => {
      const l = document.createElementNS(SVG_NS, 'line');
      l.setAttribute('x1', x1); l.setAttribute('y1', y1);
      l.setAttribute('x2', x2); l.setAttribute('y2', y2);
      for (const k in attrs) l.setAttribute(k, attrs[k]);
      this.svg.appendChild(l);
    };

    // 1. cells
    for (let y = 0; y < n; y++) for (let x = 0; x < m; x++) {
      const r = document.createElementNS(SVG_NS, 'rect');
      r.setAttribute('class', 'cell');
      r.setAttribute('x', x * CELL); r.setAttribute('y', y * CELL);
      r.setAttribute('width', CELL); r.setAttribute('height', CELL);
      r.setAttribute('fill', '#fff');
      this.svg.appendChild(r);
    }

    // 2. classify interior shared edges as crease (in HC) or slit (not)
    const ekey = (a, b) => {
      const k1 = `${a[0]},${a[1]}`, k2 = `${b[0]},${b[1]}`;
      return k1 < k2 ? `${k1}|${k2}` : `${k2}|${k1}`;
    };
    const inHC = new Set();
    for (let i = 0; i < N; i++) inHC.add(ekey(circ[i], circ[(i + 1) % N]));
    for (let y = 0; y < n; y++) for (let x = 0; x < m; x++) {
      if (x + 1 < m) {                       // shared vertical edge at x+1
        const crease = inHC.has(ekey([x, y], [x + 1, y]));
        line((x + 1) * CELL, y * CELL, (x + 1) * CELL, (y + 1) * CELL,
          crease ? { stroke: '#d22', 'stroke-width': 3, 'stroke-linecap': 'round' }
                 : { stroke: '#bbb', 'stroke-width': 1, 'stroke-dasharray': '2 3' });
      }
      if (y + 1 < n) {                       // shared horizontal edge at y+1
        const crease = inHC.has(ekey([x, y], [x, y + 1]));
        line(x * CELL, (y + 1) * CELL, (x + 1) * CELL, (y + 1) * CELL,
          crease ? { stroke: '#d22', 'stroke-width': 3, 'stroke-linecap': 'round' }
                 : { stroke: '#bbb', 'stroke-width': 1, 'stroke-dasharray': '2 3' });
      }
    }

    // 3. HC path through cell centres (dotted blue, closed)
    const pts = circ.map(c => `${c[0] * CELL + CELL / 2},${c[1] * CELL + CELL / 2}`);
    pts.push(pts[0]);
    const poly = document.createElementNS(SVG_NS, 'polyline');
    poly.setAttribute('points', pts.join(' '));
    poly.setAttribute('fill', 'none');
    poly.setAttribute('stroke', '#39c');
    poly.setAttribute('stroke-width', 1.5);
    poly.setAttribute('stroke-dasharray', '4 3');
    poly.setAttribute('opacity', 0.8);
    this.svg.appendChild(poly);

    // 4. cut edge (green, thick) — corner coords
    if (ts.cutEdge) {
      const [a, b] = ts.cutEdge;
      line(a[0] * CELL, a[1] * CELL, b[0] * CELL, b[1] * CELL,
        { stroke: '#2a8', 'stroke-width': 4, 'stroke-linecap': 'round' });
    }

    // 5. verdict label
    const v = ts.verdict;
    const t = document.createElementNS(SVG_NS, 'text');
    t.setAttribute('x', 3); t.setAttribute('y', 12);
    t.setAttribute('font-size', '10');
    t.setAttribute('font-family', 'ui-monospace, Menlo, monospace');
    t.setAttribute('fill', v.foldable ? '#2a8' : '#c33');
    t.textContent = `2-stack ${v.foldable ? '✓ foldable' : '✗ not foldable'} `
      + `(refl ${v.reflection ? '✓' : '✗'}, Tw=${ts.twistValue})`;
    this.svg.appendChild(t);
  }

  // --- Pointer dispatch ---
  onPointerDown(e) {
    e.preventDefault();
    this.svg.setPointerCapture(e.pointerId);
    const c = this.cellFromEvent(e);
    if (!this.inGrid(c)) return;
    const tool = this.app.tool;
    if (tool === 'pen' || tool === 'eraser' || tool === 'highlight') {
      this.dragState = { kind: 'paint', tool };
      this.applyPaint(c);
    } else if (tool === 'footprint') {
      this.toggleFootprint(c);
      this.dragState = { kind: 'footprintDrag', mode: this.state.footprint.has(key(c.x, c.y)) ? 'add' : 'remove' };
    } else if (tool === 'group') {
      this.toggleGroupCell(c);
    } else if (tool === 'fold') {
      const hit = this.findPlacementAt(c);
      if (hit) {
        this.app.setActiveGroup(hit.group.id);
        // Always anchor drag at the END of the chain so drag-back unfolds cleanly.
        this.dragState = {
          kind: 'fold',
          group: hit.group,
          activeIndex: hit.group.placements.length - 1,
          lastCell: c,
        };
      }
    } else if (tool === 'vector') {
      const g = this.app.activeGroup(this.state);
      if (!g) return;
      const inBase = g.baseCells.some(bc => bc.x === c.x && bc.y === c.y);
      if (!inBase) return;
      const rect = this.svg.getBoundingClientRect();
      const startPx = { x: e.clientX - rect.left, y: e.clientY - rect.top };
      this.dragState = {
        kind: 'vector',
        group: g,
        anchor: c,
        startPx,
        color: g.color,
        snapped: null,
      };
      this.render();
    }
  }

  onPointerMove(e) {
    if (!this.dragState) return;
    const c = this.cellFromEvent(e);
    const ds = this.dragState;
    if (ds.kind === 'paint') {
      if (this.inGrid(c)) this.applyPaint(c);
    } else if (ds.kind === 'footprintDrag') {
      if (!this.inGrid(c)) return;
      const k = key(c.x, c.y);
      if (ds.mode === 'add') this.state.footprint.add(k);
      else this.state.footprint.delete(k);
      this.render();
    } else if (ds.kind === 'fold') {
      if (!this.inGrid(c)) return;
      let iterations = 0;
      while (iterations++ < 24) {
        const active = ds.group.placements[ds.activeIndex];

        // Unfold-on-drag-back: if we were in active.cells last move and current cell is in the
        // parent's cells, pop the active placement.
        if (ds.activeIndex > 0) {
          const parent = ds.group.placements[ds.activeIndex - 1];
          const lastInActive = active.cells.some(cc => cc.x === ds.lastCell.x && cc.y === ds.lastCell.y);
          const nowInParent = parent.cells.some(cc => cc.x === c.x && cc.y === c.y);
          if (lastInActive && nowInParent) {
            const popped = ds.group.placements.pop();
            ds.activeIndex--;
            if (popped.foldArrow === 'L' || popped.foldArrow === 'R') ds.group.hFolds--;
            else ds.group.vFolds--;
            ds.lastCell = c;
            continue;
          }
        }

        // Fold-forward
        const dir = Fold.detectDirection(active, c);
        if (!dir) break;
        const np = Fold.makeFold(active, dir, this.state.m, this.state.n);
        if (!np) break;
        if (this.app.preventOverlap && this.overlapsExisting(np.cells)) break;
        ds.group.placements.push(np);
        ds.activeIndex = ds.group.placements.length - 1;
        if (dir === 'L' || dir === 'R') ds.group.hFolds++;
        else ds.group.vFolds++;
        ds.lastCell = c;
      }
      ds.lastCell = c;
      this.render();
    } else if (ds.kind === 'vector') {
      const rect = this.svg.getBoundingClientRect();
      const endPx = { x: e.clientX - rect.left, y: e.clientY - rect.top };
      ds.snapped = this.snapVectorFromDrag(ds.anchor, ds.startPx, endPx);
      this.render();
    }
  }

  onPointerUp(e) {
    if (!this.dragState) return;
    const ds = this.dragState;
    if (ds.kind === 'vector' && ds.snapped) {
      ds.group.vectors.push(ds.snapped);
      Fold.syncVectors(ds.group);
    }
    this.dragState = null;
    try { this.svg.releasePointerCapture(e.pointerId); } catch (_) {}
    this.render();
  }

  // --- Tool actions ---
  applyPaint(c) {
    const k = key(c.x, c.y);
    if (this.dragState.tool === 'pen') {
      const cell = this.state.cells.get(k) || {};
      cell.color = this.app.color;
      this.state.cells.set(k, cell);
    } else if (this.dragState.tool === 'eraser') {
      const cell = this.state.cells.get(k);
      if (cell) {
        delete cell.color; delete cell.highlight;
        if (!cell.color && !cell.highlight) this.state.cells.delete(k);
      }
    } else if (this.dragState.tool === 'highlight') {
      const cell = this.state.cells.get(k) || {};
      cell.highlight = this.app.color;
      this.state.cells.set(k, cell);
    }
    this.render();
  }

  toggleFootprint(c) {
    const k = key(c.x, c.y);
    if (this.state.footprint.has(k)) this.state.footprint.delete(k);
    else this.state.footprint.add(k);
    this.render();
  }

  toggleGroupCell(c) {
    const g = this.app.activeGroup(this.state);
    if (!g) { alert('Pick an active group first (or click + Group on this card).'); return; }
    if (!this.state.footprint.has(key(c.x, c.y))) {
      alert('Group cells must lie inside the footprint. Switch to Footprint tool to extend it.');
      return;
    }
    const idx = g.baseCells.findIndex(bc => bc.x === c.x && bc.y === c.y);
    if (idx >= 0) g.baseCells.splice(idx, 1);
    else g.baseCells.push({ x: c.x, y: c.y });
    Fold.resetGroup(g);
    Fold.syncVectors(g);
    this.render();
  }

  // Union of every placement-cell on this grid; for overlap-prevention.
  overlapsExisting(newCells) {
    const occupied = new Set();
    for (const g of this.state.groups) {
      for (const p of g.placements) {
        for (const c of p.cells) occupied.add(`${c.x},${c.y}`);
      }
    }
    return newCells.some(c => occupied.has(`${c.x},${c.y}`));
  }

  findPlacementAt(c) {
    for (const g of this.state.groups) {
      for (let i = 0; i < g.placements.length; i++) {
        if (g.placements[i].cells.some(cc => cc.x === c.x && cc.y === c.y)) {
          return { group: g, placementIndex: i };
        }
      }
    }
    return null;
  }
}
