// fold.js — pure geometry. No DOM access.
// A placement is { cells:[{x,y}], vectors:[{x,y,dx,dy}], parityH, parityV, foldArrow }.

const Fold = (() => {

  function bounds(cells) {
    let xMin = Infinity, xMax = -Infinity, yMin = Infinity, yMax = -Infinity;
    for (const c of cells) {
      if (c.x < xMin) xMin = c.x;
      if (c.x > xMax) xMax = c.x;
      if (c.y < yMin) yMin = c.y;
      if (c.y > yMax) yMax = c.y;
    }
    return { xMin, xMax, yMin, yMax };
  }

  // Reflect integer coord across a continuous boundary cBoundary on the same axis.
  // Cell at x has center x+0.5; mirror across boundary cBoundary gives center 2*cBoundary - (x+0.5),
  // which corresponds to integer cell x' = 2*cBoundary - 1 - x.
  function reflectScalar(v, cBoundary) {
    return 2 * cBoundary - 1 - v;
  }

  function reflectCells(cells, axis, cBoundary) {
    return cells.map(c =>
      axis === 'h'
        ? { x: reflectScalar(c.x, cBoundary), y: c.y }
        : { x: c.x, y: reflectScalar(c.y, cBoundary) }
    );
  }

  // Vector model: { x, y, edge: 'T'|'B'|'L'|'R', sign: +1|-1 }.
  // edge = which side of the cell the arrow lies on (a crease).
  // sign = direction along the edge tangent (+1 = +x for T/B, +1 = +y for L/R; in screen coords +y is down).
  const EDGE_FLIP_H = { T: 'T', B: 'B', L: 'R', R: 'L' };
  const EDGE_FLIP_V = { T: 'B', B: 'T', L: 'L', R: 'R' };

  function reflectVector(vec, axis, cBoundary) {
    if (axis === 'h') {
      return {
        x: reflectScalar(vec.x, cBoundary),
        y: vec.y,
        edge: EDGE_FLIP_H[vec.edge],
        sign: (vec.edge === 'T' || vec.edge === 'B') ? -vec.sign : vec.sign,
      };
    } else {
      return {
        x: vec.x,
        y: reflectScalar(vec.y, cBoundary),
        edge: EDGE_FLIP_V[vec.edge],
        sign: (vec.edge === 'L' || vec.edge === 'R') ? -vec.sign : vec.sign,
      };
    }
  }

  // Map drag direction to (axis, crease boundary index, parity flip, arrow char).
  function foldSpec(direction, b) {
    switch (direction) {
      case 'R': return { axis: 'h', cBoundary: b.xMax + 1, parity: 'parityH', arrow: 'R' };
      case 'L': return { axis: 'h', cBoundary: b.xMin,     parity: 'parityH', arrow: 'L' };
      case 'D': return { axis: 'v', cBoundary: b.yMax + 1, parity: 'parityV', arrow: 'D' };
      case 'U': return { axis: 'v', cBoundary: b.yMin,     parity: 'parityV', arrow: 'U' };
    }
  }

  function inBounds(cells, m, n) {
    for (const c of cells) {
      if (c.x < 0 || c.x >= m || c.y < 0 || c.y >= n) return false;
    }
    return true;
  }

  // Build a new placement by folding `active` in `direction`.
  // Returns null if the resulting cells leave the grid.
  function makeFold(active, direction, m, n) {
    const b = bounds(active.cells);
    const spec = foldSpec(direction, b);
    const newCells = reflectCells(active.cells, spec.axis, spec.cBoundary);
    if (!inBounds(newCells, m, n)) return null;
    const newVectors = active.vectors.map(v => reflectVector(v, spec.axis, spec.cBoundary));
    const placement = {
      cells: newCells,
      vectors: newVectors,
      parityH: active.parityH ^ (spec.axis === 'h' ? 1 : 0),
      parityV: active.parityV ^ (spec.axis === 'v' ? 1 : 0),
      foldArrow: spec.arrow,
      // Crease info for rendering the chevron:
      creaseAxis: spec.axis,
      creaseAt: spec.cBoundary,
      parentBounds: b,
      transformChain: active.transformChain.concat([{ axis: spec.axis, cBoundary: spec.cBoundary }]),
    };
    return placement;
  }

  // Decide whether the cursor cell triggers a fold relative to the active placement.
  // Cursor must be past one of the four edges AND within the perpendicular band of the placement.
  function detectDirection(active, cursor) {
    if (!active.cells.length) return null;
    const b = bounds(active.cells);
    const inYBand = cursor.y >= b.yMin && cursor.y <= b.yMax;
    const inXBand = cursor.x >= b.xMin && cursor.x <= b.xMax;
    if (cursor.x > b.xMax && inYBand) return 'R';
    if (cursor.x < b.xMin && inYBand) return 'L';
    if (cursor.y > b.yMax && inXBand) return 'D';
    if (cursor.y < b.yMin && inXBand) return 'U';
    return null;
  }

  function initialPlacement(baseCells) {
    return {
      cells: baseCells.map(c => ({ x: c.x, y: c.y })),
      vectors: [],
      parityH: 0, parityV: 0,
      foldArrow: null,
      creaseAxis: null, creaseAt: null, parentBounds: null,
      transformChain: [],
    };
  }

  // Apply a chain of reflections (in order) to a base vector, returning its image.
  function projectVector(baseVec, chain) {
    let v = { ...baseVec };
    for (const step of chain) {
      v = reflectVector(v, step.axis, step.cBoundary);
    }
    return v;
  }

  // Recompute per-placement vectors from the group's base vectors.
  function syncVectors(group) {
    for (const p of group.placements) {
      p.vectors = group.vectors.map(v => projectVector(v, p.transformChain));
    }
  }

  // Reset all placements to just the original (using current group.vectors as the seed).
  function resetGroup(group) {
    const orig = initialPlacement(group.baseCells);
    orig.vectors = group.vectors.map(v => ({ ...v }));
    group.placements = [orig];
    group.hFolds = 0;
    group.vFolds = 0;
  }

  return {
    bounds, reflectCells, reflectVector, projectVector, syncVectors,
    makeFold, detectDirection, initialPlacement, resetGroup,
  };
})();
