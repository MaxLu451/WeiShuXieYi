import hashlib, json, sqlite3, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, '.vendor')
from bs4 import BeautifulSoup

root=Path(__file__).resolve().parent
out=root/'season-provisional'
db=sqlite3.connect(out/'season.sqlite3')
db.executescript('''DROP TABLE IF EXISTS strategies; DROP TABLE IF EXISTS equipment;
CREATE TABLE strategies(id INTEGER PRIMARY KEY, name TEXT, character TEXT, role TEXT, details TEXT, image_url TEXT, source_entry_id INTEGER);
CREATE TABLE equipment(id INTEGER PRIMARY KEY, name TEXT, tier TEXT, price TEXT, details TEXT, image_url TEXT, source_entry_id INTEGER);''')
urls=set()
def direct_rows(table):
    parent=table.find('tbody',recursive=False) or table
    return parent.find_all('tr',recursive=False)
def cells(row): return row.find_all(['td','th'],recursive=False)
def image(node):
    im=node.find('img') if node else None
    return im.get('src','') if im else ''
for entry_id, category, html in db.execute('SELECT id,category,source_html FROM entries').fetchall():
    table=BeautifulSoup(html,'html.parser').find('table')
    rows=direct_rows(table)
    if category=='策略':
        if len(rows)<2: continue
        c=cells(rows[0]); last=cells(rows[-1])
        if len(c)<3 or not last: continue
        character=c[0].get_text('',strip=True); role=c[1].get_text('',strip=True)
        name=last[-1].get_text('',strip=True); details=c[2].get_text('',strip=True); url=image(c[0])
        db.execute('INSERT INTO strategies(name,character,role,details,image_url,source_entry_id) VALUES(?,?,?,?,?,?)',(name,character,role,details,url,entry_id))
    else:
        if len(rows)<3: continue
        first=cells(rows[0]); third=cells(rows[2])
        if len(first)<2 or len(third)<2: continue
        tier=first[0].get_text('',strip=True).replace('等阶',''); name=first[1].get_text('',strip=True)
        price=third[0].get_text('',strip=True); details=third[1].get_text('\n',strip=True); url=image(table)
        db.execute('INSERT INTO equipment(name,tier,price,details,image_url,source_entry_id) VALUES(?,?,?,?,?,?)',(name,tier,price,details,url,entry_id))
    if url: urls.add(url)
db.commit()
assets=out/'images';assets.mkdir(exist_ok=True)
def fetch(url):
    filename=hashlib.sha256(url.encode()).hexdigest()+'.img'; path=assets/filename
    try:
        data=urllib.request.urlopen(url,timeout=20).read() if not path.exists() else path.read_bytes()
        if not (data.startswith(b'\x89PNG\r\n\x1a\n') or data.startswith(b'\xff\xd8\xff') or data.startswith(b'RIFF')): return (url,'','invalid image')
        if not path.exists(): path.write_bytes(data)
        return (url,'images/'+filename,'ok')
    except Exception as exc: return (url,'',str(exc)[:150])
with ThreadPoolExecutor(max_workers=4) as pool: results=list(pool.map(fetch,sorted(urls)))
db.executemany('INSERT OR REPLACE INTO images VALUES(?,?,?)',results);db.commit()
for name in ('strategies','equipment'):
    print(name,db.execute('SELECT count(*) FROM '+name).fetchone()[0])
    print('missing',db.execute('SELECT count(*) FROM '+name+" WHERE name='' OR details=''").fetchone()[0])
print('assets ok',sum(s=='ok' for _,_,s in results),'failed',sum(s!='ok' for _,_,s in results))
db.close()
