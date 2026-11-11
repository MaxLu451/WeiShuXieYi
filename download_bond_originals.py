"""Fetch original PRTS alliance icons, preserving the existing thumbnail URLs."""
import hashlib, sqlite3, urllib.request
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

root=Path(__file__).resolve().parent/'season-provisional'
db=sqlite3.connect(root/'season.sqlite3')
for name,url in db.execute('SELECT name,icon_url FROM bonds').fetchall():
    parts=urlsplit(url);segments=parts.path.split('/')
    if len(segments)<6 or segments[1]!='thumb':continue
    original=urlunsplit((parts.scheme,parts.netloc,'/'+'/'.join(segments[2:-1]),parts.query,''))
    try:
        data=urllib.request.urlopen(original,timeout=20).read()
        if not data.startswith(b'\x89PNG\r\n\x1a\n'):raise ValueError('Not a PNG')
        filename=hashlib.sha256(original.encode()).hexdigest()+'.png';(root/'images'/filename).write_bytes(data)
        db.execute('INSERT OR REPLACE INTO images(url,path,status) VALUES(?,?,?)',(original,'images/'+filename,'ok'))
        db.execute('UPDATE bonds SET icon_url=? WHERE name=?',(original,name))
        print(name,'ok',len(data))
    except Exception as e:print(name,'failed',str(e))
db.commit();db.close()
