def evaluate(ranked_by_case, cases, ks=(1,3,5,10,20,50,100,200)):
    out = {f'hit@{k}':0.0 for k in ks}; out.update({f'recall@{k}':0.0 for k in ks}); out['mrr']=0.0
    n=len(cases)
    for c in cases:
        r = ranked_by_case[c['id']]; g=set(c['gold'])
        pos = [i for i,a in enumerate(r) if a in g]
        out['mrr'] += (1/(pos[0]+1) if pos else 0)/n
        for k in ks:
            top=set(r[:k]); out[f'hit@{k}'] += (len(top&g)>0)/n; out[f'recall@{k}'] += (len(top&g)/len(g))/n
    return out
def fmt(name, m, ks=(1,3,5,10,20,50,100,200)):
    return f"{name:28s} MRR {m['mrr']:.3f} | " + ' '.join(f"h@{k} {m[f'hit@{k}']:.2f}" for k in ks) + ' | ' + ' '.join(f"r@{k} {m[f'recall@{k}']:.2f}" for k in ks)
