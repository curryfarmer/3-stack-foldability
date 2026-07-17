import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import righttri as RT, prove_obstruction as PO
from hunt_foldable import holes

def etype(lat, a, b):
    (p, q) = lat.shared_edge_cart(a, b)
    return 'long' if ((p[0]-q[0])**2+(p[1]-q[1])**2)**0.5 > 0.85 else 'short'

def side_info(ch):
    region = sorted(set().union(*[set(c) for c in ch]))
    lat = RT.RightTriLattice(cells=region)
    A0,B0,C0 = ch[0][0], ch[1][0], ch[2][0]
    A1,B1,C1 = ch[0][-1], ch[1][-1], ch[2][-1]
    bmid = (A1 in lat.adj[B1] and C1 in lat.adj[B1] and C1 not in lat.adj[A1])
    if not bmid:
        return False, 'exit-mid!=B'
    ab = (etype(lat,A0,B0), etype(lat,A1,B1)); bc = (etype(lat,B0,C0), etype(lat,B1,C1))
    return (ab[0]==ab[1] and bc[0]==bc[1]), 'AB %s->%s BC %s->%s'%(ab+bc)

if __name__ == '__main__':
    # Brute-force K=12 scan (triple-nested growth, several minutes) -- guarded so importing this
    # module (e.g. seam_filter.seam_type's lazy `import sidematch_scan`) never triggers it.
    lat, S, back = RT.build_ambient_right(12, 'HL')
    arm1, m, arm2 = S
    mids = [p for p in PO.grow(lat, m, 12, {arm1, arm2}) if p[1] == back]
    rows = []
    for pm in mids:
        um = set(pm)
        for pa in PO.grow(lat, arm1, 12, um|{arm2}):
            ua = um | set(pa)
            for pc in PO.grow(lat, arm2, 12, ua):
                if not PO.is_trapezoid(lat, [pa[-1], pm[-1], pc[-1]]):
                    continue
                ch = [list(pa), list(pm), list(pc)]
                # RT.pair_tw scores with loop-index (path) sigma, so `foldable` here correctly labels
                # the K=12 tetrakis JAMs (the bipartite sigma read a spurious Tw=0 -> false foldable).
                # NB: the committed results/tri_K12_hl_all.json snapshot predates this fix; test_tri
                # _reference.py locks that FROZEN snapshot, so a rerun here will diverge from it.
                L = RT.pair_tw(ch)
                tw = tuple(round(L[k]['Tw']) for k in ('AB','BC','AC'))
                sm, info = side_info(ch)
                hf = not bool(holes(lat, set(pa)|set(pm)|set(pc)))
                rows.append({'chains': ch, 'footprint':[pa[0],pm[0],pc[0]],
                             'tw': tw, 'foldable': all(x==0 for x in tw),
                             'holefree': hf, 'sidematch': bool(sm), 'sideinfo': info})
    print('closing folds:', len(rows), flush=True)
    fold = [r for r in rows if r['foldable']]
    sm = [r for r in rows if r['sidematch']]
    fsm = [r for r in rows if r['foldable'] and r['sidematch']]
    fsmh = [r for r in fsm if r['holefree']]
    print('foldable:%d  side-matching:%d  foldable&side-match:%d  +hole-free:%d'%(len(fold),len(sm),len(fsm),len(fsmh)),flush=True)
    from collections import Counter
    print('sideinfo among ALL closing:', dict(Counter(r['sideinfo'] for r in rows)), flush=True)
    print('tw among side-matching:', dict(Counter(r['tw'] for r in sm)), flush=True)
    os.makedirs(os.path.join(os.path.dirname(__file__), '..', '..', 'results'), exist_ok=True)
    json.dump(rows, open(os.path.join(os.path.dirname(__file__),'..','..','results','tri_K12_hl_all.json'),'w'), default=list)
    print('done', flush=True)
