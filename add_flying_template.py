import json, sys
from pathlib import Path
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'.vendor'))
import cv2, numpy as np
source=root/'素材'/'微信图片_20261111151105_49_64.png'
image=cv2.imdecode(np.fromfile(str(source),dtype=np.uint8),cv2.IMREAD_COLOR)
if image is None: raise SystemExit('Cannot read source image')
image=cv2.resize(image,(1597,857))
directory=root/'season-provisional'/'recognition'; meta=directory/'templates.json'
items=json.loads(meta.read_text(encoding='utf8'))
items=[x for x in items if x['file']!='flying.png']
cv2.imencode('.png',image[611:643,1128:1160])[1].tofile(str(directory/'flying.png'))
items.append({'name':'飞行','kind':'enemy','state':'enemy','file':'flying.png'})
meta.write_text(json.dumps(items,ensure_ascii=False,indent=2),encoding='utf8')
print('Added flying enemy template')
