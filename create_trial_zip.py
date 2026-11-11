from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
root=Path(__file__).resolve().parent
source=root/'release-build-v2'/'GarrisonAssistant'
archive=root/'卫戍协议助手-Windows试用版-新版.zip'
with ZipFile(archive,'w',compression=ZIP_DEFLATED,compresslevel=6,allowZip64=True) as output:
    for path in sorted(source.rglob('*')):
        if path.is_file():output.write(path,Path('GarrisonAssistant')/path.relative_to(source))
with ZipFile(archive) as check:
    bad=check.testzip()
    if bad:raise RuntimeError('Invalid archive member: '+bad)
    names=set(check.namelist())
    for required in ('GarrisonAssistant/GarrisonAssistant.exe','GarrisonAssistant/试用版说明.txt','GarrisonAssistant/season-provisional/season.sqlite3','GarrisonAssistant/season-provisional/recognition/templates.json'):
        if required not in names:raise RuntimeError('Missing archive member: '+required)
    print('Archive entries:',len(names),'size MB:',round(archive.stat().st_size/1024/1024,1),'integrity: OK')
