// search.js — exhaustive 3-stack enumerator. Pure compute, no DOM.
// Dual mode:
//   * Main thread: include via <script src="search.js"></script> → uses window.Search.
//   * Worker:      importScripts('fold.js'); importScripts('search.js') → listens on self.onmessage.
// Math primitives from fold.js (Fold.makeFold, Fold.reflectVector, Fold.syncVectors, Fold.initialPlacement).

const Search = (() => {

  const cellKey = (x, y) => x * 1000 + y;   // m,n ≤ 999 so this is collision-free

  // --- Stage 2: footprint enumeration ---

  // L base cells: corner at (0,0), arms at (1,0) and (0,1). Rotation 0 = no rotation.
  // Apply 4 rotations of D4 about origin then translate by anchor.
  const L_BASE = [
    [{x:0,y:0},{x:1,y:0},{x:0,y:1}],     // rot 0: corner top-left, arms right+down
    [{x:0,y:0},{x:0,y:1},{x:-1,y:0}],    // rot 1 (90° CW around corner)
    [{x:0,y:0},{x:-1,y:0},{x:0,y:-1}],   // rot 2 (180°)
    [{x:0,y:0},{x:0,y:-1},{x:1,y:0}],    // rot 3 (270° CW)
  ];

  function enumerateFootprints(m, n, opts) {
    const out = [];
    if (opts.shapes.L) {
      for (let rot = 0; rot < 4; rot++) {
        const tpl = L_BASE[rot];
        for (let ay = 0; ay < n; ay++) {
          for (let ax = 0; ax < m; ax++) {
            const cells = tpl.map(c => ({x: c.x + ax, y: c.y + ay}));
            if (cells.every(c => c.x >= 0 && c.x < m && c.y >= 0 && c.y < n)) {
              if (!opts.allowNonCorner) {
                // Restrict to anchors where the bounding box hits (0,0).
                const xs = cells.map(c => c.x), ys = cells.map(c => c.y);
                if (Math.min(...xs) !== 0 || Math.min(...ys) !== 0) continue;
              }
              // cellRoles: corner first, then arms (lex-sorted).
              const corner = cells[0];
              const arms = cells.slice(1).sort((a,b) => a.x - b.x || a.y - b.y);
              out.push({
                shape: 'L', rotation: rot, anchor: {x: ax, y: ay},
                cells: [corner, ...arms],
                cellRoles: ['corner', 'arm', 'arm'],
              });
            }
          }
        }
      }
    }
    if (opts.shapes.Rect) {
      // Horizontal 1x3: end0=(0,0), mid=(1,0), end1=(2,0)
      // Vertical 3x1:   end0=(0,0), mid=(0,1), end1=(0,2)
      for (const orient of ['H', 'V']) {
        const tpl = orient === 'H'
          ? [{x:0,y:0},{x:1,y:0},{x:2,y:0}]
          : [{x:0,y:0},{x:0,y:1},{x:0,y:2}];
        for (let ay = 0; ay < n; ay++) {
          for (let ax = 0; ax < m; ax++) {
            const cells = tpl.map(c => ({x: c.x + ax, y: c.y + ay}));
            if (cells.every(c => c.x >= 0 && c.x < m && c.y >= 0 && c.y < n)) {
              if (!opts.allowNonCorner) {
                if (ax !== 0 || ay !== 0) continue;
              }
              out.push({
                shape: 'Rect', rotation: orient === 'H' ? 0 : 1, anchor: {x: ax, y: ay},
                cells,
                cellRoles: ['end', 'mid', 'end'],
              });
            }
          }
        }
      }
    }
    return out;
  }

  // --- Stage 3: decomposition enumeration ---

  function enumerateDecompositions(footprint, opts) {
    const out = [];
    const cells = footprint.cells;
    if (footprint.shape === 'L') {
      const corner = cells[0], armA = cells[1], armB = cells[2];
      if (opts.decomps['2+1']) {
        // 2-stack on the two arms (which include the corner-adjacent arm + corner? Let's reconsider).
        // L cells: corner, armA, armB. The two "arm" cells from cellRoles are adjacent to corner; they may
        // NOT be adjacent to each other. We need a 2-stack baseCells = 2 ADJACENT cells. Adjacency check:
        const adj = (a,b) => Math.abs(a.x-b.x)+Math.abs(a.y-b.y) === 1;
        // Three pairs: (corner,armA), (corner,armB), (armA,armB).
        const pairs = [[corner,armA,armB],[corner,armB,armA],[armA,armB,corner]];
        for (const [p0, p1, tail] of pairs) {
          if (!adj(p0, p1)) continue;
          out.push({
            decomp: '2+1',
            chains: [
              { kind: '2chain', baseCells: [p0, p1], targetIndices: [] },
              { kind: '1chain', baseCells: [tail],   targetIndices: [] },
            ],
          });
        }
      }
      if (opts.decomps['1+1+1']) {
        // Corner first, arms sorted lex (already in canonical order from enumerateFootprints).
        out.push({
          decomp: '1+1+1',
          chains: [
            { kind: '1chain', baseCells: [corner], targetIndices: [] },
            { kind: '1chain', baseCells: [armA],   targetIndices: [] },
            { kind: '1chain', baseCells: [armB],   targetIndices: [] },
          ],
        });
      }
    } else { // Rect
      const [end0, mid, end1] = cells;
      if (opts.decomps['2+1']) {
        out.push({
          decomp: '2+1',
          chains: [
            { kind: '2chain', baseCells: [end0, mid], targetIndices: [] },
            { kind: '1chain', baseCells: [end1],      targetIndices: [] },
          ],
        });
        out.push({
          decomp: '2+1',
          chains: [
            { kind: '2chain', baseCells: [mid, end1], targetIndices: [] },
            { kind: '1chain', baseCells: [end0],      targetIndices: [] },
          ],
        });
      }
      if (opts.decomps['1+1+1']) {
        out.push({
          decomp: '1+1+1',
          chains: [
            { kind: '1chain', baseCells: [end0], targetIndices: [] },
            { kind: '1chain', baseCells: [mid],  targetIndices: [] },
            { kind: '1chain', baseCells: [end1], targetIndices: [] },
          ],
        });
      }
    }
    return out;
  }

  // --- Stage 4: DFS ---

  // Connectivity / partition pruner.
  // Given a reservation Set<key>, grid m×n, and remaining chain sizes (multiset),
  // return false if the unclaimed region's connected components cannot be partitioned
  // into the remaining chain sizes.
  function connectivityOK(reserved, m, n, remainingSizes) {
    const componentSizes = [];
    const visited = new Set();
    for (let y = 0; y < n; y++) {
      for (let x = 0; x < m; x++) {
        const k = cellKey(x, y);
        if (reserved.has(k) || visited.has(k)) continue;
        // BFS
        let size = 0;
        const stack = [k];
        while (stack.length) {
          const cur = stack.pop();
          if (visited.has(cur)) continue;
          visited.add(cur);
          size++;
          const cx = Math.floor(cur / 1000), cy = cur % 1000;
          for (const [dx, dy] of [[1,0],[-1,0],[0,1],[0,-1]]) {
            const nx = cx + dx, ny = cy + dy;
            if (nx < 0 || nx >= m || ny < 0 || ny >= n) continue;
            const nk = cellKey(nx, ny);
            if (reserved.has(nk) || visited.has(nk)) continue;
            stack.push(nk);
          }
        }
        componentSizes.push(size);
      }
    }
    // Each component must be partitionable into a subset of remainingSizes (each used at most once globally).
    // We need to check: ∃ a partition of remainingSizes into groups, one group per component, sums match.
    // For v1 with at most 2 remaining sizes (often 1), this is tractable by trying all subsets per component.
    return canPartition(componentSizes, remainingSizes);
  }

  function canPartition(componentSizes, sizes) {
    // Try assigning subsets of `sizes` to each component such that each subset sums to that component's size.
    // sizes is small (≤ 3); we use bitmask enumeration.
    const N = sizes.length;
    const componentTotal = componentSizes.reduce((a,b)=>a+b, 0);
    const sizesTotal = sizes.reduce((a,b)=>a+b, 0);
    if (componentTotal !== sizesTotal) return false;

    // Memoise: assigned bitmask → array of remaining components-to-assign indices.
    // Greedy: process components in order; for each, try every subset of unassigned sizes that sums to it.
    function recur(idx, used) {
      if (idx === componentSizes.length) return used === (1 << N) - 1;
      const target = componentSizes[idx];
      for (let sub = (1 << N) - 1; sub >= 0; sub--) {
        if (sub & used) continue;          // overlap with already-used sizes
        if (sub === 0) continue;
        let s = 0;
        for (let i = 0; i < N; i++) if (sub & (1 << i)) s += sizes[i];
        if (s !== target) continue;
        if (recur(idx + 1, used | sub)) return true;
      }
      return false;
    }
    return recur(0, 0);
  }

  // Stage 4 driver. Calls onCandidate for each leaf with a deep-cloned solution.
  function searchDecomposition(m, n, K, decomposition, onCandidate, ctx) {
    const chains = decomposition.chains.map(c => ({
      kind: c.kind,
      baseCells: c.baseCells.map(b => ({x: b.x, y: b.y})),
      placements: [],
      foldArrows: [],
    }));
    const totalCells = m * n;

    // Deterministic ordering: largest chain first, then by base lex.
    const order = chains.map((_, i) => i).sort((a, b) => {
      const ca = chains[a], cb = chains[b];
      const sa = ca.baseCells.length * K - (ca.baseCells.length === 2 ? 0 : 0); // 2K vs K
      const sb = cb.baseCells.length * K - (cb.baseCells.length === 2 ? 0 : 0);
      if (sa !== sb) return sb - sa;
      return ca.baseCells[0].x - cb.baseCells[0].x || ca.baseCells[0].y - cb.baseCells[0].y;
    });
    // chainSize[i] = number of cells the chain occupies once unfolded = K * |baseCells|
    const chainSize = chains.map(c => K * c.baseCells.length);

    const reserved = new Set();

    function searchChains(idx) {
      ctx.nodeCount++;
      if (ctx.cancelled) return;
      if (idx === chains.length) {
        if (reserved.size === totalCells) {
          ctx.coveredCount++;
          onCandidate(chains);
        }
        return;
      }
      const realIdx = order[idx];
      const chain = chains[realIdx];
      const base = chain.baseCells;
      // Seed: every base cell must be free
      for (const c of base) {
        if (reserved.has(cellKey(c.x, c.y))) return;
      }
      for (const c of base) reserved.add(cellKey(c.x, c.y));
      chain.placements = [Fold.initialPlacement(base)];
      chain.foldArrows = [];
      dfsChain(idx, realIdx, 1);
      for (const c of base) reserved.delete(cellKey(c.x, c.y));
      chain.placements = [];
      chain.foldArrows = [];
    }

    function dfsChain(orderIdx, realIdx, depth) {
      if (ctx.cancelled) return;
      if (depth === K) {
        // This chain done; check pruning and recurse to next chain
        const remainingSizes = [];
        for (let i = orderIdx + 1; i < chains.length; i++) {
          remainingSizes.push(chainSize[order[i]]);
        }
        if (remainingSizes.length === 0 || connectivityOK(reserved, m, n, remainingSizes)) {
          searchChains(orderIdx + 1);
        }
        return;
      }
      const chain = chains[realIdx];
      const active = chain.placements[chain.placements.length - 1];
      for (const dir of ['L','R','U','D']) {
        if (ctx.cancelled) return;
        const np = Fold.makeFold(active, dir, m, n);
        if (!np) continue;
        let collide = false;
        for (const c of np.cells) {
          if (reserved.has(cellKey(c.x, c.y))) { collide = true; break; }
        }
        if (collide) continue;
        for (const c of np.cells) reserved.add(cellKey(c.x, c.y));
        chain.placements.push(np);
        chain.foldArrows.push(dir);
        ctx.candidateCount++;
        dfsChain(orderIdx, realIdx, depth + 1);
        chain.foldArrows.pop();
        chain.placements.pop();
        for (const c of np.cells) reserved.delete(cellKey(c.x, c.y));
      }
    }

    searchChains(0);
  }

  // --- Stage 5: parity (vector-symmetry condition, orientation-aware) ---
  // The A/B vector lies ALONG the inter-block crease. For the two vectors (one per side) to
  // stay on the same side after folding, the per-chain count of folds whose crease line is
  // PARALLEL to the A/B crease must be even (the perpendicular count is then forced odd,
  // since total folds K-1 is odd).
  //
  // Note on axes: an L/R fold (nH) creases on a VERTICAL line; a U/D fold (nV) on a HORIZONTAL
  // line. So "folds parallel to the A/B crease" are the ones whose crease line shares the
  // A/B crease's orientation.
  //
  // Crease orientation is derived from footprint geometry — the adjacency between the two
  // chains' base cells:
  //   horizontally-adjacent bases (dx) -> A/B crease VERTICAL  -> parallel folds are L/R (nH) -> require nH even
  //   vertically-adjacent bases  (dy) -> A/B crease HORIZONTAL -> parallel folds are U/D (nV) -> require nV even
  // Only the unique-crease 2+1 case is orientation-derived; 1+1+1 (L corner has two
  // perpendicular creases) falls back to the legacy nH-even/nV-odd rule pending its own spec.
  function parallelFoldAxis(chains) {
    if (chains.length !== 2) return null;   // only 2+1 has a single inter-block crease
    const A = chains[0].baseCells, B = chains[1].baseCells;
    for (const a of A) for (const b of B) {
      if (Math.abs(a.x - b.x) + Math.abs(a.y - b.y) === 1) {
        return a.x !== b.x ? 'H' : 'V';     // 'H' => nH (parallel to vertical crease) even; 'V' => nV even
      }
    }
    return null;
  }

  function parityCheck(chains) {
    const axis = parallelFoldAxis(chains);
    for (const c of chains) {
      let nH = 0, nV = 0;
      for (const a of c.foldArrows) {
        if (a === 'L' || a === 'R') nH++;
        else nV++;
      }
      c.nH = nH; c.nV = nV;
      if (axis === 'H') {            // vertical A/B crease: parallel folds = L/R (nH) must be even
        if (nH % 2 !== 0) return false;
      } else if (axis === 'V') {     // horizontal A/B crease: parallel folds = U/D (nV) must be even
        if (nV % 2 !== 0) return false;
      } else {                       // legacy fallback (1+1+1)
        if (nH % 2 !== 0) return false;
        if (nV % 2 !== 1) return false;
      }
    }
    return true;
  }

  // --- Stage 5.5: exit footprint ---
  // Union of every chain's LAST placement must form a 3-cell shape congruent to startShape (rotations allowed).
  // 2+1: 2-chain last (2 cells) + 1-chain last (1 cell) = 3.
  // 1+1+1: three 1-chain lasts = 3.
  // Shape classification by bbox of 3 distinct cells:
  //   bbox (2,0) or (0,2) → Rect (1×3 line)
  //   bbox (1,1)         → L (3 cells inside a 2×2)
  //   otherwise          → reject
  function exitFootprintCheck(chains, startShape) {
    const cells = [];
    for (const c of chains) {
      const last = c.placements[c.placements.length - 1];
      for (const cell of last.cells) cells.push({ x: cell.x, y: cell.y });
    }
    if (cells.length !== 3) return false;
    const seen = new Set();
    for (const c of cells) {
      const k = c.x * 100000 + c.y;
      if (seen.has(k)) return false;
      seen.add(k);
    }
    const xs = cells.map(c => c.x), ys = cells.map(c => c.y);
    const dx = Math.max(...xs) - Math.min(...xs);
    const dy = Math.max(...ys) - Math.min(...ys);
    let shape;
    if ((dx === 2 && dy === 0) || (dx === 0 && dy === 2)) shape = 'Rect';
    else if (dx === 1 && dy === 1) shape = 'L';
    else return false;
    return shape === startShape;
  }

  // --- Stage 6: reflection (orientation-aware) ---
  // Seed the SHARED crease between each adjacent pair of chains as one world segment, reflect each
  // side to its far end, and require the images to coincide as oriented grid segments. Covers 2+1
  // (one pair) and 1+1+1 (the pairwise footprint creases). The old gate seeded an arbitrary T,+1 at
  // baseCells[0] and compared lossy (edge,sign) labels, which false-passed jamming 2+1 folds
  // (e.g. 6x5#1) — see Fold.reflectionVerdict.
  function reflectionCheck(chains) {
    const res = Fold.reflectionVerdict(chains);
    for (const d of res.pairs) {
      chains[d.i].finalVector = { edge: d.imgI.edge, sign: d.imgI.sign };
      chains[d.j].finalVector = { edge: d.imgJ.edge, sign: d.imgJ.sign };
    }
    for (const c of chains) {
      if (c.finalVector === undefined) c.finalVector = null;
    }
    return res.pass;
  }

  // --- Stage 7: twist (Calugareanu-White-Fuller, Tw = 0) ---
  // The physical model is ONE connected HC; the footprint creases are fused, so the three
  // chains share two rigid hubs (start footprint + exit footprint). Each PAIR of chains
  // therefore forms a 2-stack-style closed loop (hub -> chain i -> hub -> chain j -> back).
  // Foldable without entanglement iff every pairwise loop has Tw = 0 (closed-loop turn-angle
  // balance, the validated notwist.py primitive).
  //
  // Only DECIDED for all-1chain decomps (1+1+1 / I-shape): a 1-chain's placement centroids
  // are a clean unit-cell panel path, so the loop turn angles are physical. For decomps with
  // a 2-chain (2+1), the per-panel HC ordering inside the domino is unresolved, so a centroid
  // path is NOT a valid panel path (yields non-physical twist) -> verdict left undecided.
  function chainCenterPath(chain) {
    return chain.placements.map(p => {
      let sx = 0, sy = 0;
      for (const c of p.cells) { sx += c.x + 0.5; sy += c.y + 0.5; }
      const k = p.cells.length || 1;
      return [sx / k, sy / k];
    });
  }

  // Closed-loop turn-angle balance over chain i forward + chain j reversed (wrap closes the
  // loop through the two fused hubs). Tw = sum(odd) - sum(even) over alternating vertices.
  function pairLoopTwist(pathA, pathB) {
    const pts = pathA.concat(pathB.slice().reverse());
    const n = pts.length;
    let odd = 0, even = 0;
    for (let i = 0; i < n; i++) {
      const p1 = pts[i], p2 = pts[(i + 1) % n], p3 = pts[(i + 2) % n];
      const v1x = p2[0] - p1[0], v1y = p2[1] - p1[1];
      const v2x = p3[0] - p2[0], v2y = p3[1] - p2[1];
      let ang = 0;
      if (Math.hypot(v1x, v1y) > 1e-9 && Math.hypot(v2x, v2y) > 1e-9) {
        const dot = v1x * v2x + v1y * v2y;
        const cross = v1x * v2y - v1y * v2x;
        ang = Math.round(Math.atan2(cross, dot) * 180 / Math.PI);
      }
      ang *= 2;
      if (i % 2 === 0) even += ang; else odd += ang;
    }
    return odd - even;
  }

  // --- 2+1 jump-strand twist (Model B) — byte-for-byte mirror of py/twist_jump.py. ---
  // Keep the two in lockstep: doubled atan2 turn (NO per-term rounding), sigma = (-1)^i along the
  // loop, round the SUM only. Foldable <=> Tw == 0; Tw = +-720 is a self-twist jam. NOT pairLoopTwist
  // (that rounds each angle; the jump-strand must not).
  function ccCell(c) { return [c.x + 0.5, c.y + 0.5]; }

  function strandPath(placements, idx) {
    return placements.map(p => ccCell(p.cells[idx]));
  }

  function loopTerms(pts) {
    const n = pts.length, terms = [];
    for (let i = 0; i < n; i++) {
      const p1 = pts[i], p2 = pts[(i + 1) % n], p3 = pts[(i + 2) % n];
      const v1x = p2[0] - p1[0], v1y = p2[1] - p1[1];
      const v2x = p3[0] - p2[0], v2y = p3[1] - p2[1];
      let ang = 0;
      if (Math.hypot(v1x, v1y) > 1e-9 && Math.hypot(v2x, v2y) > 1e-9) {
        const dot = v1x * v2x + v1y * v2y;
        const cross = v1x * v2y - v1y * v2x;
        ang = Math.atan2(cross, dot) * 180 / Math.PI;   // doubled below; NO per-term rounding
      }
      terms.push(2 * ang);
    }
    return terms;
  }

  function twOf(terms) {
    let t = 0;
    for (let i = 0; i < terms.length; i++) t += (i % 2 ? 1 : -1) * terms[i];
    return Math.round(t * 1e6) / 1e6;                   // round the SUM only (== Python round(t, 6))
  }

  function loopTw(body, path1) {
    return twOf(loopTerms(body.concat(path1.slice().reverse())));
  }

  function classifyStep(p, q) {
    const dx = Math.abs(q[0] - p[0]), dy = Math.abs(q[1] - p[1]);
    if (dx + dy === 1) return 'unit';
    if (dx === 1 && dy === 1) return 'DIAG';
    if ((dx === 0 && dy === 2) || (dx === 2 && dy === 0)) return '2JMP';
    return 'far';
  }

  // Canonical strand = the domino cell whose two hub seams are non-diagonal (cosmetic — Tw is
  // idx-independent — but pinned so JS and Python label the same strand).
  function pickCanonIdx(placements2, path1) {
    for (const idx of [0, 1]) {
      const sp = strandPath(placements2, idx);
      const k = sp.length;
      const loop = sp.concat(path1.slice().reverse());
      const s1 = classifyStep(loop[k - 1], loop[k]);
      const s2 = classifyStep(loop[2 * k - 1], loop[0]);
      if (s1 !== 'DIAG' && s2 !== 'DIAG') return idx;
    }
    return 0;
  }

  // 2+1 (one domino + one monomino) jump-strand twist; returns twistCheck shape or null if not 2+1.
  function twist2plus1(chains) {
    if (chains.length !== 2) return null;
    const lens = chains.map(c => (c.baseCells ? c.baseCells.length : 1));
    if (!((lens[0] === 2 && lens[1] === 1) || (lens[0] === 1 && lens[1] === 2))) return null;
    const i2 = lens[0] === 2 ? 0 : 1, i1 = 1 - i2;
    const path1 = strandPath(chains[i1].placements, 0);
    const idx = pickCanonIdx(chains[i2].placements, path1);
    const tw = loopTw(strandPath(chains[i2].placements, idx), path1);
    return { decided: true, pass: Math.abs(tw) < 1e-6, pairs: [{ i: i2, j: i1, tw }] };
  }

  function twistCheck(chains) {
    // 1+1+1 (all single-cell chains): pairwise centroid-loop twist (the historic path, unchanged).
    if (chains.every(c => (c.baseCells ? c.baseCells.length : 1) === 1)) {
      const paths = chains.map(chainCenterPath);
      const pairs = [];
      let pass = true;
      for (let i = 0; i < chains.length; i++) {
        for (let j = i + 1; j < chains.length; j++) {
          const tw = pairLoopTwist(paths[i], paths[j]);
          pairs.push({ i, j, tw });
          if (tw !== 0) pass = false;
        }
      }
      return { decided: true, pass, pairs };
    }
    // 2+1 (one domino + one monomino): jump-strand twist (Model B). Foldable <=> Tw == 0.
    const res = twist2plus1(chains);
    if (res) return res;
    // anything else stays undecided (non-filtering).
    return { decided: false, pass: null, pairs: [] };
  }

  // --- Stage 8: D4 canonical hash ---

  // D4 elements: 4 rotations × {identity, flip-H}. m,n swap under 90/270° rotation.
  function applyTransform(t, x, y, m, n) {
    // t: { rot: 0..3, flip: 0|1 }
    let X = x, Y = y;
    if (t.flip) X = m - 1 - X;
    switch (t.rot) {
      case 0: return { x: X, y: Y };
      case 1: return { x: Y, y: m - 1 - X };          // rot 90 CW: (x,y) → (y, m-1-x); width becomes n
      case 2: return { x: m - 1 - X, y: n - 1 - Y };  // rot 180
      case 3: return { x: n - 1 - Y, y: X };          // rot 270 CW
    }
  }

  // Direction permutation under transform.
  function transformArrow(t, dir) {
    let d = dir;
    if (t.flip) d = ({L:'R',R:'L',U:'U',D:'D'})[d];
    for (let i = 0; i < t.rot; i++) {
      d = ({L:'U',U:'R',R:'D',D:'L'})[d];
    }
    return d;
  }

  function canonicalHash(footprint, chains, m, n) {
    let best = null;
    for (let rot = 0; rot < 4; rot++) {
      for (let flip = 0; flip < 2; flip++) {
        const t = { rot, flip };
        const fp = footprint.cells
          .map(c => applyTransform(t, c.x, c.y, m, n))
          .map(c => [c.x, c.y]).sort((a,b) => a[0]-b[0] || a[1]-b[1]);
        const chainSigs = chains.map(c => ({
          kind: c.kind,
          base: c.baseCells
            .map(b => applyTransform(t, b.x, b.y, m, n))
            .map(c2 => [c2.x, c2.y]).sort((a,b) => a[0]-b[0] || a[1]-b[1]),
          arrows: c.foldArrows.map(a => transformArrow(t, a)),
        }));
        chainSigs.sort((a, b) => {
          if (a.kind !== b.kind) return a.kind < b.kind ? -1 : 1;
          return JSON.stringify(a.base) < JSON.stringify(b.base) ? -1 : 1;
        });
        const sig = JSON.stringify({ fp, chains: chainSigs });
        if (best === null || sig < best) best = sig;
      }
    }
    return best;
  }

  // --- Top-level runner ---
  // opts: { m, n, shapes:{L,Rect}, decomps:{'2+1','1+1+1'}, allowNonCorner, dedup }
  // callbacks: { onProgress, onSolution, onDone, onError, isCancelled }
  function run(opts, callbacks) {
    const { m, n } = opts;
    const ctx = {
      nodeCount: 0,
      candidateCount: 0,
      coveredCount: 0,
      exitPass: 0,
      parityPass: 0,
      reflPass: 0,
      afterDedup: 0,
      twistPass: 0,
      footprintsTried: 0,
      footprintsTotal: 0,
      decompCount: 0,
      cancelled: false,
      lastTick: Date.now(),
    };
    const dedupMap = new Map();
    let nextId = 1;

    // Arithmetic gate
    if ((m * n) % 6 !== 0) { callbacks.onError && callbacks.onError('mn not divisible by 6'); callbacks.onDone(ctx); return; }
    const K = (m * n) / 3;
    if (K % 2 !== 0) { callbacks.onError && callbacks.onError('K = mn/3 must be even'); callbacks.onDone(ctx); return; }
    if (n < 4) { callbacks.onError && callbacks.onError('n < 4 (conjectured rejection)'); callbacks.onDone(ctx); return; }

    const footprints = enumerateFootprints(m, n, opts);
    ctx.footprintsTotal = footprints.length;

    function tick(force = false) {
      const now = Date.now();
      if (!force && (now - ctx.lastTick) < 250) return;
      ctx.lastTick = now;
      if (callbacks.isCancelled && callbacks.isCancelled()) ctx.cancelled = true;
      callbacks.onProgress && callbacks.onProgress({
        footprintsTried: ctx.footprintsTried,
        footprintsTotal: ctx.footprintsTotal,
        decompCount: ctx.decompCount,
        candidates: ctx.candidateCount,
        coveredCount: ctx.coveredCount,
        exitPass: ctx.exitPass,
        parityPass: ctx.parityPass,
        reflPass: ctx.reflPass,
        afterDedup: ctx.afterDedup,
        twistPass: ctx.twistPass,
      });
    }

    for (const footprint of footprints) {
      if (ctx.cancelled) break;
      ctx.footprintsTried++;
      const decomps = enumerateDecompositions(footprint, opts);
      for (const decomp of decomps) {
        if (ctx.cancelled) break;
        ctx.decompCount++;
        searchDecomposition(m, n, K, decomp, (chains) => {
          // Coverage already verified at leaf. Deep-clone before downstream stages.
          const cloned = chains.map(c => ({
            kind: c.kind,
            baseCells: c.baseCells.map(b => ({x: b.x, y: b.y})),
            placements: c.placements.map(p => ({
              cells: p.cells.map(cc => ({x: cc.x, y: cc.y})),
              parityH: p.parityH, parityV: p.parityV,
              foldArrow: p.foldArrow,
              creaseAxis: p.creaseAxis, creaseAt: p.creaseAt,
              transformChain: p.transformChain.map(s => ({axis: s.axis, cBoundary: s.cBoundary})),
            })),
            foldArrows: c.foldArrows.slice(),
          }));
          if (!exitFootprintCheck(cloned, footprint.shape)) { tick(); return; }
          ctx.exitPass++;
          if (!parityCheck(cloned)) { tick(); return; }
          ctx.parityPass++;
          if (!reflectionCheck(cloned)) { tick(); return; }
          ctx.reflPass++;
          const hash = canonicalHash(footprint, cloned, m, n);
          if (opts.dedup) {
            if (dedupMap.has(hash)) { tick(); return; }
            dedupMap.set(hash, true);
          }
          ctx.afterDedup++;
          // Twist verdict (non-filtering): annotate, don't drop. Pairwise-loop twist;
          // decided only for 1+1+1 (all 1-chains), else pending.
          const twist = twistCheck(cloned);
          if (twist.decided && twist.pass) ctx.twistPass++;
          const sol = {
            id: nextId++,
            footprint: {
              shape: footprint.shape,
              rotation: footprint.rotation,
              anchor: footprint.anchor,
              cells: footprint.cells.map(c => ({x: c.x, y: c.y})),
            },
            decomposition: decomp.decomp,
            chains: cloned.map(c => ({
              kind: c.kind,
              baseCells: c.baseCells,
              foldArrows: c.foldArrows,
              nH: c.nH, nV: c.nV,
              finalVector: c.finalVector,
            })),
            twistPairs: twist.pairs,
            verdict: { arithmetic: true, exitFootprint: true, parity: true, reflection: true, twist: twist.decided ? twist.pass : null },
            canonicalHash: hash,
          };
          callbacks.onSolution && callbacks.onSolution(sol);
          tick();
        }, ctx);
        tick();
      }
      tick();
    }
    tick(true);
    callbacks.onDone && callbacks.onDone(ctx);
  }

  return {
    run,
    enumerateFootprints,
    enumerateDecompositions,
    canonicalHash,
    parityCheck,
    reflectionCheck,
    twistCheck,
  };
})();

// Worker mode: if we're in a Worker context, wire onmessage.
if (typeof self !== 'undefined' && typeof window === 'undefined' && typeof importScripts === 'function') {
  let cancelled = false;
  self.onmessage = (ev) => {
    const msg = ev.data;
    if (msg.type === 'cancel') { cancelled = true; return; }
    if (msg.type === 'run') {
      cancelled = false;
      Search.run(msg.opts, {
        isCancelled: () => cancelled,
        onProgress: (p) => self.postMessage({ type: 'progress', payload: p }),
        onSolution: (s) => self.postMessage({ type: 'solution', payload: s }),
        onDone: (ctx) => self.postMessage({ type: 'done', payload: {
          candidates: ctx.candidateCount, coveredCount: ctx.coveredCount,
          exitPass: ctx.exitPass,
          parityPass: ctx.parityPass, reflPass: ctx.reflPass, afterDedup: ctx.afterDedup,
          twistPass: ctx.twistPass,
          footprintsTried: ctx.footprintsTried, footprintsTotal: ctx.footprintsTotal,
          cancelled: ctx.cancelled,
        }}),
        onError: (e) => self.postMessage({ type: 'error', payload: e }),
      });
    }
  };
}
