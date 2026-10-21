import sqlite3, os, re, zipfile, hashlib, collections
db=sqlite3.connect("n.db")
out=[]  # (category, path, size, reason)
def full(p):
    h=hashlib.sha1()
    with open(p,'rb') as f:
        while b:=f.read(8<<20): h.update(b)
    return h.hexdigest()
# 1. misfiled Taskmaster episode: full-hash confirm
a=r"N:\Plex_Media\TV\Taskmaster\Series 13\taskmaster.s13e06.the.75th.question.1080p.hdtv.h264-darkflix.mkv"
b=r"N:\Plex_Media\TV\The Mindy Project\Season 6\taskmaster.s13e06.the.75th.question.1080p.hdtv.h264-darkflix.mkv"
if full(a)==full(b): out.append(("misfiled-dup",b,os.path.getsize(b),"full-hash identical to copy in Taskmaster\Series 13"))
else: print("TASKMASTER HASH MISMATCH - skipped")
# 2. zips fully present (every member same size) in the extracted folder
for p,n in db.execute(r"select path,name from f where dir='N:\Downloads' and ext='.zip'"):
    d=os.path.join(r"N:\Downloads",os.path.splitext(n)[0])
    if not os.path.isdir(d): continue
    try: members=[i for i in zipfile.ZipFile(p).infolist() if not i.is_dir()]
    except Exception: continue
    ok=all(any(os.path.isfile(c) and os.path.getsize(c)==i.file_size for c in (os.path.join(d,i.filename), os.path.join(d,*i.filename.split('/')[1:]) if '/' in i.filename else None) if c) for i in members)
    if ok and members: out.append(("extracted-zip",p,os.path.getsize(p),f"all {len(members)} members present, same sizes, in {os.path.basename(d)}\\"))
    elif os.path.getsize(p)>50<<20: print("zip NOT fully verified, kept:",n)
# 3. full-hash exact dups where every copy is in Downloads root: keep shortest/non-(n) name
groups=collections.defaultdict(list)
for g,p,s,m in db.execute("select * from dup where method='full'"): groups[g].append((p,s))
for v in groups.values():
    if not all(os.path.dirname(p)==r"N:\Downloads" for p,_ in v): continue
    def rank(p):
        n=os.path.basename(p); return (n.endswith('.crdownload'), bool(re.search(r' \(\d+\)\.[^.]+$',n)), len(n))
    v.sort(key=lambda x:rank(x[0]))
    for p,s in v[1:]: out.append(("exact-dup",p,s,"identical to "+os.path.basename(v[0][0])))
# 4. samples + RARBG stubs
for p,s in db.execute(r"select path,size from f where (path like 'N:\Plex_Media\%' or path like 'N:\Plex Custom Vids\%') and (path like '%\Sample\%' or name='RARBG_DO_NOT_MIRROR.exe')"):
    out.append(("torrent-junk",p,s,"sample clip / RARBG marker exe"))
# 5. VC++ 2008 redist leftovers in N:\ root
for p,s in db.execute(r"select path,size from f where dir='N:\' and (name like 'eula.%.txt' or name like 'install%' or name in ('globdata.ini','vcredist.bmp','VC_RED.cab','VC_RED.MSI'))"):
    out.append(("vcredist-2008",p,s,"VC++ 2008 installer files extracted to drive root"))
# 6. dead/empty folders (conservative)
for d in [r"N:\msdownld.tmp", r"N:\SteamLibrary", r"N:\tf2 demos\prec demos", r"N:\Plex_Media\TV\Taskmaster\Taskmaster - New Years Treat",
          r"N:\Flash drive\.Spotlight-V100", r"N:\Flash drive\.Trashes"] + \
         [r"N:\RAW video files\\"[:-1]+x for x in ["9343b833-e7af-42ea-8a61-31bc41eefe2b","Borderlands The Pre-Sequel","Cuphead","Desktop","Fallout 4","Overwatch","Tdbswd56spcap","Team Fortress 2","Wolfenstein  The Old Blood"]]:
    if os.path.isdir(d):
        sz=sum(os.path.getsize(os.path.join(r,f)) for r,_,fs in os.walk(d) for f in fs)
        out.append(("dead-folder",d,sz,"not a registered Steam library" if d.endswith("SteamLibrary") else "empty or macOS index junk"))
with open("recycle_list.tsv","w",encoding="utf-8") as f:
    for c,p,s,r in out: f.write(f"{c}\t{p}\t{s}\t{r}\n")
tot=collections.Counter(); n=collections.Counter()
for c,p,s,r in out: tot[c]+=s; n[c]+=1
for c in tot: print(f"{c:15s}{n[c]:5d} items {tot[c]/2**30:7.2f} GB")
print("TOTAL",len(out),round(sum(tot.values())/2**30,2),"GB")
