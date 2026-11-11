"""Create a source-preserving, provisional PRTS data package."""
import json, sqlite3, sys
from pathlib import Path
from urllib.parse import urljoin
sys.path.insert(0, str(Path(__file__).parent / '.vendor'))
from bs4 import BeautifulSoup

root = Path(__file__).parent
source = root / 'prts-source.html'
out = root / 'season-provisional'
out.mkdir(exist_ok=True)
soup = BeautifulSoup(source.read_text(encoding='utf-8'), 'html.parser')
content = soup.select_one('.mw-parser-output')
db = sqlite3.connect(out / 'season.sqlite3')
db.executescript('DROP TABLE IF EXISTS records; DROP TABLE IF EXISTS assets; CREATE TABLE records (id INTEGER PRIMARY KEY, section TEXT, subsection TEXT, kind TEXT, text TEXT, html TEXT); CREATE TABLE assets (id INTEGER PRIMARY KEY, record_id INTEGER, url TEXT, alt TEXT);')
section = subsection = ''
for element in content.children:
    if not getattr(element, 'name', None):
        continue
    if element.name == 'h2':
        section, subsection = element.get_text(' ', strip=True).replace('[编辑]', ''), ''
    elif element.name == 'h3':
        subsection = element.get_text(' ', strip=True).replace('[编辑]', '')
    elif element.name in ('div', 'table', 'p', 'ul'):
        text = element.get_text(' ', strip=True)
        if not text and not element.find('img'):
            continue
        cur = db.execute('INSERT INTO records(section,subsection,kind,text,html) VALUES(?,?,?,?,?)', (section, subsection, element.name, text, str(element)))
        for img in element.find_all('img'):
            src = img.get('data-src') or img.get('src') or ''
            if src:
                db.execute('INSERT INTO assets(record_id,url,alt) VALUES(?,?,?)', (cur.lastrowid, urljoin('https://prts.wiki/', src), img.get('alt','')))
db.commit()
counts = {t: db.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in ('records','assets')}
db.close()
(out / 'manifest.json').write_text(json.dumps({'season':'卫戍协议·规程','status':'provisional_source_archive','source':'https://prts.wiki/w/卫戍协议·规程/PRTS盟约记录','counts':counts,'note':'原始页面分段及图片链接，尚未转换为可用于筛选的干员、盟约结构化数据；图片未下载。'}, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(counts))
