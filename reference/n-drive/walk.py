import os, sys, sqlite3, time
db = sqlite3.connect(sys.argv[1])
db.execute("drop table if exists f"); db.execute("drop table if exists d")
db.execute("create table f(path text, dir text, name text, ext text, size int, mtime real)")
db.execute("create table d(path text, nfiles int, nsub int, mtime real)")
SKIP = {"$RECYCLE.BIN", "System Volume Information"}
t=time.time(); rows=[]; drows=[]
def onerr(e): print("ERR", e, file=sys.stderr)
for root, dirs, files in os.walk("N:\\", onerror=onerr):
    if root == "N:\\": dirs[:] = [d for d in dirs if d not in SKIP]
    try: dm = os.stat(root).st_mtime
    except OSError: dm = 0
    drows.append((root, len(files), len(dirs), dm))
    for n in files:
        p = os.path.join(root, n)
        try: st = os.stat(p)
        except OSError as e: onerr(e); continue
        rows.append((p, root, n, os.path.splitext(n)[1].lower(), st.st_size, st.st_mtime))
    if len(rows) > 50000:
        db.executemany("insert into f values(?,?,?,?,?,?)", rows); rows=[]
db.executemany("insert into f values(?,?,?,?,?,?)", rows)
db.executemany("insert into d values(?,?,?,?)", drows)
db.commit()
print("done", time.time()-t, "s", db.execute("select count(*), sum(size) from f").fetchone(), len(drows), "dirs")
