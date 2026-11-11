"""Copy only application data into the PyInstaller directory."""
import shutil,sqlite3
from pathlib import Path
root=Path(__file__).resolve().parent
source=root/'season-provisional';dest=root/'release-build-v2'/'GarrisonAssistant';pack=dest/'season-provisional';pack.mkdir(parents=True,exist_ok=True)
for folder in ('images','recognition'):
    shutil.copytree(source/folder,pack/folder,dirs_exist_ok=True)
shutil.copy2(source/'manifest.json',pack/'manifest.json')
shutil.copy2(root/'试用版说明.txt',dest/'试用版说明.txt')
with sqlite3.connect(source/'season.sqlite3') as src, sqlite3.connect(pack/'season.sqlite3') as dst:
    src.backup(dst)
    for table in ('records','assets','entries'):
        dst.execute('DROP TABLE IF EXISTS '+table)
    dst.execute('ALTER TABLE operators DROP COLUMN source_html')
    dst.commit()
    dst.execute('VACUUM')
print('Distribution data prepared:',pack)
