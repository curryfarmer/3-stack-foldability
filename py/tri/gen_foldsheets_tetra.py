import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import righttri as RT, prove_obstruction as PO
from hunt_foldable import holes
import foldsheet_tri as FS
import render_general as RG

lat, S, back = RT.build_ambient_right(12, 'HL')
arm1, m, arm2 = S
mids = [p for p in PO.grow(lat, m, 12, {arm1, arm2}) if p[1] == back]
foldable = []
for pm in mids:
    um = set(pm)
    for pa in PO.grow(lat, arm1, 12, um | {arm2}):
        ua = um | set(pa)
        for pc in PO.grow(lat, arm2, 12, ua):
            if not PO.is_trapezoid(lat, [pa[-1], pm[-1], pc[-1]]):
                continue
            L = RT.pair_tw([pa, pm, pc])
            if all(abs(L[k]['Tw']) < 1e-6 for k in L):
                hh = bool(holes(lat, set(pa) | set(pm) | set(pc)))
                foldable.append({'chains': [list(pa), list(pm), list(pc)],
                                 'footprint': [pa[0], pm[0], pc[0]], 'holefree': not hh})
print('foldable found:', len(foldable), '| hole-free:', sum(1 for f in foldable if f['holefree']), flush=True)
outdir = os.path.join(os.path.dirname(__file__), '..', '..', 'results')
json.dump(foldable, open(os.path.join(outdir, 'tri_foldable_K12_hl.json'), 'w'), default=list, indent=1)
hf = [f for f in foldable if f['holefree']]
for i, f in enumerate(hf[:2], 1):
    ch = [[tuple(t) for t in c] for c in f['chains']]
    fp = [tuple(t) for t in f['footprint']]
    p = FS.make_sheet(RT.RightTriLattice, RT.vcart, RT.tile_cart, RT.sigma, ch, fp,
                      '45-45-90 FOLDABLE fold sheet #%d (K=12)' % i, 'tetra_foldsheet_%d.png' % i, 12)
    print('sheet', os.path.basename(p), flush=True)
    p2 = RG.render(RT, ch, fp, '45-45-90 foldable #%d (chains)' % i,
                   'tetra_foldable_hf_%d.png' % i,
                   '1+1+1 on 45-45-90 (K=12, 36 tiles)\nAB=0 BC=0 AC=0 -> FOLDABLE\nhole-free')
    print('render', os.path.basename(p2), flush=True)
print('done', flush=True)
