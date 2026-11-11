"""Basic reproducible checks for the provisional season package."""
import json, sqlite3
from pathlib import Path

root=Path(__file__).resolve().parent/'season-provisional'
db=sqlite3.connect(root/'season.sqlite3')
problems=[]
def check(condition, message):
    if not condition: problems.append(message)
check(db.execute('PRAGMA integrity_check').fetchone()[0]=='ok','SQLite integrity check failed')
check(not db.execute('SELECT DISTINCT bond_name FROM operator_bonds WHERE bond_name NOT IN (SELECT name FROM bonds)').fetchall(),'Unknown operator bond')
for operator_id,names in db.execute('SELECT id,names_json FROM operators'):
    check(bool(json.loads(names)),f'Operator row {operator_id} has no names')
    check(bool(db.execute('SELECT 1 FROM operator_bonds WHERE operator_id=?',(operator_id,)).fetchone()),f'Operator row {operator_id} has no bonds')
for url,path,status in db.execute('SELECT url,path,status FROM images'):
    check(status=='ok' and bool(path) and (root/path).is_file(),f'Missing image: {url}')
for table in ('strategies','equipment'):
    check(db.execute('SELECT COUNT(*) FROM '+table+' WHERE name=? OR details=?',('','')).fetchone()[0]==0,f'Empty {table} fields')
counts={t:db.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in ('operators','operator_bonds','bonds','strategies','equipment','images')}
print(json.dumps({'counts':counts,'problems':problems},ensure_ascii=False,indent=2))
raise SystemExit(bool(problems))
