"""Remove hidden website tooltip text from the visible alliance descriptions."""
import sqlite3,sys
from pathlib import Path
root=Path(__file__).resolve().parent;sys.path.insert(0,str(root/'.vendor'))
from bs4 import BeautifulSoup
soup=BeautifulSoup((root/'prts-source.html').read_text(encoding='utf8'),'html.parser')
db=sqlite3.connect(root/'season-provisional'/'season.sqlite3');updated=0
for table in soup.select('table')[:51]:
    if 'mw-collapsible' in table.get('class',[]):continue
    body=table.find('tbody',recursive=False) or table;rows=body.find_all('tr',recursive=False)
    if not rows or '激活所需人数' not in rows[0].get_text(' ',strip=True):continue
    cells=rows[0].find_all(['td','th'],recursive=False)
    if len(cells)<2:continue
    name=cells[0].get_text('',strip=True);cell=BeautifulSoup(str(cells[1]),'html.parser')
    for tip in cell.select('[data-append-to][style*="display:none"]'):tip.decompose()
    result=db.execute('UPDATE bonds SET effect=? WHERE name=?',(cell.get_text('',strip=True),name));updated+=result.rowcount
db.commit();db.close();print('Updated alliance descriptions:',updated)
