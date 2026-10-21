import sqlite3, hashlib, collections, sys, time
db=sqlite3.connect(sys.argv[1])
CH=1<<20
def partial(p, size):
    h=hashlib.sha1()
    with open(p,'rb') as f:
        for off in (0, size//2, max(0,size-CH)):
            f.seek(off); h.update(f.read(CH))
    return h.hexdigest()
def full(p):
    h=hashlib.sha1()
    with open(p,'rb') as f:
        while b:=f.read(8*CH): h.update(b)
    return h.hexdigest()
rows=db.execute(r"""select path,size from f where size>0 and path not like 'N:\Steam\%' and path not like 'N:\.emu\%'
  and size in (select size from f where size>0 and path not like 'N:\Steam\%' and path not like 'N:\.emu\%' group by size having count(*)>1)""").fetchall()
print(len(rows),"files share a size with another", sum(s for _,s in rows)/2**30,"GB", flush=True)
bysize=collections.defaultdict(list)
for p,s in rows: bysize[s].append(p)
db.execute("drop table if exists dup"); db.execute("create table dup(grp text, path text, size int, method text)")
t=time.time(); fullbytes=0
for s,ps in bysize.items():
    g=collections.defaultdict(list)
    for p in ps:
        try: g[partial(p,s) if s>3*CH else full(p)].append(p)
        except OSError as e: print("ERR",e)
    for k,v in g.items():
        if len(v)<2: continue
        method="full" if s<=3*CH else "partial"
        if s>3*CH and s<=512*CH:   # confirm with full hash up to 512MB
            g2=collections.defaultdict(list)
            for p in v: g2[full(p)].append(p); fullbytes+=s
            groups=[x for x in g2.values() if len(x)>1]; method="full"
        else: groups=[v]
        for i,grp in enumerate(groups):
            for p in grp: db.execute("insert into dup values(?,?,?,?)",(f"{s}-{k}-{i}",p,s,method))
db.commit()
print("done",time.time()-t,"s; full-hashed",fullbytes/2**30,"GB")
