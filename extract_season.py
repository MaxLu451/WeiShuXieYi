import hashlib, json, re, sqlite3, sys, urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, '.vendor')
from bs4 import BeautifulSoup

root = Path(__file__).resolve().parent
out = root / 'season-provisional'
soup = BeautifulSoup((root / 'prts-source.html').read_text(encoding='utf-8'), 'html.parser')
tables = soup.select('table')
db = sqlite3.connect(out / 'season.sqlite3')
db.executescript('''DROP TABLE IF EXISTS operators; DROP TABLE IF EXISTS operator_bonds; DROP TABLE IF EXISTS bonds; DROP TABLE IF EXISTS entries; DROP TABLE IF EXISTS images;
CREATE TABLE operators(id INTEGER PRIMARY KEY, tier TEXT, names_json TEXT, trait_type TEXT, trait_normal TEXT, trait_elite TEXT, source_html TEXT);
CREATE TABLE operator_bonds(operator_id INTEGER, bond_name TEXT, icon_url TEXT);
CREATE TABLE bonds(name TEXT PRIMARY KEY, category TEXT, effect TEXT, icon_url TEXT);
CREATE TABLE entries(id INTEGER PRIMARY KEY, category TEXT, text TEXT, source_html TEXT);
CREATE TABLE images(url TEXT PRIMARY KEY, path TEXT, status TEXT);
''')
urls=set()
def imgurl(node):
    img=node.find('img') if node else None
    return img.get('src','') if img else ''
def rows(table):
    body=table.find('tbody',recursive=False) or table
    return body.find_all('tr',recursive=False)

for t in tables:
    heading=t.find('th')
    tier=heading.get_text(' ',strip=True).replace(' ','') if heading else ''
    if not re.fullmatch(r'[ⅠⅡⅢⅣⅤⅥ]阶干员',tier): continue
    for row in rows(t)[2:]:
        original_row = str(row)
        cells=row.find_all('td',recursive=False)
        if len(cells)!=3: continue
        names=[]
        for a in cells[0].find_all('a'):
            img=a.find('img',id='charicon')
            if img:
                url=img.get('src',''); names.append({'name':a.get('title',''), 'avatar_url':url}); urls.add(url)
        bondcell=cells[1]
        bondnames=[x.strip() for x in bondcell.stripped_strings if x.strip()]
        icons=[i.get('src','') for i in bondcell.find_all('img')]
        trait=cells[2]
        label=trait.find('div',recursive=False)
        category=label.get_text(' ',strip=True) if label else ''
        if label: label.extract()
        elite=trait.find('p',recursive=False)
        elite_text=elite.get_text('',strip=True) if elite else ''
        if elite: elite.extract()
        normal=trait.get_text('',strip=True)
        cur=db.execute('INSERT INTO operators(tier,names_json,trait_type,trait_normal,trait_elite,source_html) VALUES(?,?,?,?,?,?)',(tier[0],json.dumps(names,ensure_ascii=False),category,normal,elite_text,original_row))
        for i,name in enumerate(bondnames):
            icon=icons[i] if i<len(icons) else ''
            db.execute('INSERT INTO operator_bonds VALUES(?,?,?)',(cur.lastrowid,name,icon)); urls.add(icon)

for index,t in enumerate(tables[:51]):
    if 'mw-collapsible' in t.get('class',[]): continue
    r=rows(t)
    if not r or '激活所需人数' not in r[0].get_text(' ',strip=True): continue
    cells=r[0].find_all(['td','th'],recursive=False)
    if len(cells)<2: continue
    name=cells[0].get_text('',strip=True)
    icon=imgurl(cells[0]); urls.add(icon)
    # Exclude nested operator listings from the description.
    effect_cell=BeautifulSoup(str(cells[1]),'html.parser')
    for tooltip in effect_cell.select('[data-append-to][style*="display:none"]'):tooltip.decompose()
    effects=[effect_cell.get_text('',strip=True)]
    for row in r[1:]:
        if row.find('table'): continue
        effects.append(row.get_text('',strip=True))
    db.execute('INSERT OR REPLACE INTO bonds VALUES(?,?,?,?)',(name,'核心盟约' if index<20 else '附加盟约','\n'.join(effects),icon))

for t in tables:
    h=t.find_previous('h2')
    section=h.get_text(' ',strip=True) if h else ''
    if not ('策略报告' in section or '装备数据库' in section): continue
    if t.find_parent('table'): continue
    db.execute('INSERT INTO entries(category,text,source_html) VALUES(?,?,?)',('策略' if '策略' in section else '装备',t.get_text(' ',strip=True),str(t)))
db.commit()
urls.discard('')
assets=out/'images'; assets.mkdir(exist_ok=True)
def download(url):
    name=hashlib.sha256(url.encode()).hexdigest()+'.png'; path=assets/name
    try:
        if not path.exists():
            data=urllib.request.urlopen(url,timeout=20).read()
            if not data.startswith(b'\x89PNG\r\n\x1a\n'): return url,'','invalid image'
            path.write_bytes(data)
        return url,'images/'+name,'ok'
    except Exception as e: return url,'',str(e)[:150]
with ThreadPoolExecutor(max_workers=6) as pool:
    results=list(pool.map(download,sorted(urls)))
db.executemany('INSERT OR REPLACE INTO images VALUES(?,?,?)',results)
db.commit()
for name in ('operators','operator_bonds','bonds','entries','images'):
    print(name,db.execute('SELECT count(*) FROM '+name).fetchone()[0])
print('images downloaded',sum(r[2]=='ok' for r in results),'failed',sum(r[2]!='ok' for r in results))
print('missing names',db.execute("SELECT count(*) FROM operators WHERE names_json='[]'").fetchone()[0])
print('missing bonds',db.execute('SELECT count(*) FROM operators o WHERE NOT EXISTS (SELECT 1 FROM operator_bonds b WHERE b.operator_id=o.id)').fetchone()[0])
db.close()
