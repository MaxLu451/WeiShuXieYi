"""Build screenshot templates from the user's supplied example images."""
import json, sys
from pathlib import Path
sys.path.insert(0,'.vendor')
import cv2, numpy as np

root=Path(__file__).resolve().parent
temp=Path.home()/'AppData/Local/Temp'
samples=[
('codex-clipboard-8e4aefde-ce13-4fe2-952a-7f5cf1c7a677.png',220,370,603,768,['炎','伊比利亚','维多利亚','卡西米尔','萨尔贡','莱塔尼亚','阿戈尔','谢拉格','乌萨斯','叙拉古'],['精准','坚守','助力','远见','奇迹','投资人','突袭','调和','协防干员','独行','绝技','迅捷','灵巧','不屈','聚合','奥术'],['频次','折射']),
('codex-clipboard-0dc10d4f-44d5-45af-aded-bc9f486c9130.png',203,350,590,754,['维多利亚','谢拉格','乌萨斯','叙拉古','萨尔贡','伊比利亚','莱塔尼亚','炎','阿戈尔','卡西米尔'],['灵巧','坚守','奇迹','投资人','突袭','不屈','调和','协防干员','独行','绝技','奥术','精准','迅捷','助力','远见','聚合'],['持续','频次']),
('codex-clipboard-84f466ff-eecf-4a55-9213-38da599db753.png',234,383,620,784,['萨尔贡','叙拉古','炎','伊比利亚','阿戈尔','乌萨斯','卡西米尔','谢拉格','莱塔尼亚','维多利亚'],['迅捷','坚守','助力','投资人','突袭','调和','协防干员','独行','绝技','聚合','奥术','精准','灵巧','远见','奇迹','不屈'],['元素','复苏']),
('codex-clipboard-91fe39bb-dd2e-4a81-b38f-24eb59ed8379.png',202,350,590,755,['维多利亚','乌萨斯','伊比利亚','卡西米尔','莱塔尼亚','炎','萨尔贡','谢拉格','叙拉古','阿戈尔'],['精准','灵巧','坚守','投资人','突袭','调和','协防干员','独行','绝技','聚合','奥术','迅捷','助力','远见','奇迹','不屈'],['隐匿','复苏']),
('codex-clipboard-75a9a9c8-90de-4061-9ebe-24b106862b88.png',235,384,621,786,['伊比利亚','卡西米尔','乌萨斯','萨尔贡','叙拉古','谢拉格','维多利亚','莱塔尼亚','阿戈尔','炎'],['精准','迅捷','远见','奇迹','投资人','突袭','调和','协防干员','独行','绝技','奥术','灵巧','坚守','助力','不屈','聚合'],['持续','隐匿']),
(str(Path.home()/'Desktop/微信图片_20261111151002_48_64.png'),229,378,615,779,['炎','叙拉古','乌萨斯','卡西米尔','伊比利亚','阿戈尔','莱塔尼亚','谢拉格','维多利亚','萨尔贡'],['灵巧','助力','远见','奇迹','投资人','不屈','调和','协防干员','独行','绝技','聚合','精准','迅捷','坚守','突袭','奥术'],['复苏','隐匿'])]
templates=[]; labels=[];states=[]; kinds=[]
for filename,top,bottom,small1,small2,cores,smalls,enemies in samples:
    data=np.fromfile(str(temp/filename),dtype=np.uint8);image=cv2.imdecode(data,cv2.IMREAD_COLOR)
    if image is None: raise RuntimeError('Missing '+filename)
    image=cv2.resize(image,(1597,857))
    corepos=[(224,top),(338,top),(450,top),(280,bottom),(394,bottom),(712,top),(826,top),(940,top),(768,bottom),(882,bottom)]
    smallpos=[(139+98*i,small1) for i in range(10)]+[(139+98*i,small2) for i in range(6)]
    for kind,names,positions in [('core',cores,corepos),('small',smalls,smallpos)]:
        for i,(name,(x,y)) in enumerate(zip(names,positions)):
            templates.append(image[y-20:y+20,x-20:x+20]);labels.append(name);kinds.append(kind);states.append('available' if (i<5 if kind=='core' else i<10 or i==10) else 'banned')
    for i,name in enumerate(enemies):
        x,y=1144,570+57*i
        templates.append(image[y-16:y+16,x-16:x+16]);labels.append(name);kinds.append('enemy');states.append('enemy')
extra=root/'素材'/'微信图片_20261111151105_49_64.png'
image=cv2.imdecode(np.fromfile(str(extra),dtype=np.uint8),cv2.IMREAD_COLOR)
if image is None: raise RuntimeError('Missing '+str(extra))
image=cv2.resize(image,(1597,857)); x,y=1144,627
templates.append(image[y-16:y+16,x-16:x+16]);labels.append('飞行');kinds.append('enemy');states.append('enemy')
out=root/'season-provisional'/'recognition';out.mkdir(exist_ok=True)
for i,im in enumerate(templates):cv2.imencode('.png',im)[1].tofile(str(out/f'{i:03d}.png'))
(out/'templates.json').write_text(json.dumps([{'name':n,'kind':k,'state':s,'file':f'{i:03d}.png'} for i,(n,k,s) in enumerate(zip(labels,kinds,states))],ensure_ascii=False,indent=2),encoding='utf8')
print('templates',len(templates))
