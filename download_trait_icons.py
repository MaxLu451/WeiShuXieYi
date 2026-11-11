"""Download the trait type icons referenced in the saved source rows."""
import hashlib, sqlite3, sys, urllib.request
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'.vendor'))
from bs4 import BeautifulSoup
pack=root/'season-provisional'; db=sqlite3.connect(pack/'season.sqlite3')
db.execute('CREATE TABLE IF NOT EXISTS trait_icons (trait_type TEXT PRIMARY KEY, icon_url TEXT)')
for category,html in db.execute('SELECT trait_type,source_html FROM operators GROUP BY trait_type').fetchall():
    soup=BeautifulSoup(html,'html.parser');cells=soup.find_all('td',recursive=True);img=cells[-1].find('img') if cells else None
    if not img:print(category,'missing icon');continue
    url=img.get('src','');parts=urlsplit(url);segments=parts.path.split('/')
    original=urlunsplit((parts.scheme,parts.netloc,'/'+'/'.join(segments[2:-1]),parts.query,'')) if len(segments)>5 and segments[1]=='thumb' else url
    try:
        data=urllib.request.urlopen(original,timeout=20).read()
        if not data.startswith(b'\x89PNG\r\n\x1a\n'):raise ValueError('Not a PNG')
        filename=hashlib.sha256(original.encode()).hexdigest()+'.png';(pack/'images'/filename).write_bytes(data)
        db.execute('INSERT OR REPLACE INTO images VALUES(?,?,?)',(original,'images/'+filename,'ok'));db.execute('INSERT OR REPLACE INTO trait_icons VALUES(?,?)',(category,original));print(category,'ok')
    except Exception as exc:print(category,'failed',str(exc))
db.commit();db.close()
