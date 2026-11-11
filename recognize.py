"""Locate and recognize alliance icons in full or tightly cropped screenshots."""
import json,sqlite3,sys
from functools import lru_cache
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'.vendor'))
import cv2,numpy as np

class RecognitionError(Exception):pass

def _normalize(mask):
    points=cv2.findNonZero(mask)
    if points is None:return np.zeros((64,64),bool)
    x,y,w,h=cv2.boundingRect(points);crop=mask[y:y+h,x:x+w];factor=54/max(w,h)
    image=cv2.resize(crop,(max(1,round(w*factor)),max(1,round(h*factor))),interpolation=cv2.INTER_AREA)
    result=np.zeros((64,64),np.uint8);top=(64-image.shape[0])//2;left=(64-image.shape[1])//2;result[top:top+image.shape[0],left:left+image.shape[1]]=image
    return result>100

@lru_cache(maxsize=4)
def _assets(directory,revision):
    root=Path(directory);db=sqlite3.connect(root/'season.sqlite3')
    try:
        files=dict(db.execute("SELECT url,path FROM images WHERE status='ok'"));shapes={}
        for name,category,url in db.execute('SELECT name,category,icon_url FROM bonds'):
            if url not in files:raise RecognitionError('赛季数据缺少盟约图标：'+name)
            image=cv2.imdecode(np.fromfile(str(root/files[url]),np.uint8),cv2.IMREAD_UNCHANGED)
            if image is None or len(image.shape)!=3 or image.shape[2]<4:raise RecognitionError('盟约图标无效：'+name)
            shapes[name]=(category,_normalize(image[:,:,3]))
    finally:db.close()
    screenshot=[];manifest=root/'recognition'/'templates.json'
    if manifest.exists():
        for item in json.loads(manifest.read_text(encoding='utf8')):
            if item.get('kind') not in ('core','small'):continue
            path=root/'recognition'/item['file']
            if not path.is_file():continue
            image=cv2.imdecode(np.fromfile(str(path),np.uint8),cv2.IMREAD_COLOR)
            if image is not None:screenshot.append((item,image))
    return shapes,screenshot

def _locate(image):
    hsv=cv2.cvtColor(image,cv2.COLOR_BGR2HSV);mask=cv2.inRange(hsv,(65,110,80),(100,255,255));mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
    _,_,stats,_=cv2.connectedComponentsWithStats(mask);points=[]
    for x,y,w,h,area in stats[1:]:
        if w>=30 and h>=30 and .65<w/h<1.5 and area>400:points.append((float(x+w/2),float(y+h/2),float((w+h)/2)))
    candidates=[p[2] for p in points if p[2]>45]
    if len(candidates)<12:raise RecognitionError('截图中可识别的盟约图标不完整')
    diameter=float(np.median(candidates));points=[p for p in points if .7*diameter<p[2]<1.3*diameter];groups=[]
    for point in sorted(points,key=lambda p:p[1]):
        if groups and abs(point[1]-np.median([p[1] for p in groups[-1]]))<diameter*.25:groups[-1].append(point)
        else:groups.append([point])
    if not groups:raise RecognitionError('未找到盟约图标')
    row=max(groups,key=len)
    if len(row)!=10:raise RecognitionError('未能完整定位附加盟约，请截入全部盟约图标')
    row=sorted(row);step=float(np.median(np.diff([p[0] for p in row])));left=float(np.median([p[0]-i*step for i,p in enumerate(row)]));ys=float(np.median([p[1] for p in row]));d=float(np.median([p[2] for p in row]))
    if not .95*d<step<1.7*d:raise RecognitionError('附加盟约位置不完整')
    bottom_points=[p for p in points if abs(p[0]-left)<d*.35 and ys+d*1.5<p[1]<ys+d*3]
    if len(bottom_points)!=1:raise RecognitionError('未能完整定位附加盟约的下排图标')
    bottom=bottom_points[0][1]
    upper=[g for g in groups if len(g)>=2 and np.median([p[1] for p in g])<ys-d]
    if len(upper)==1 and len(upper[0])==5:
        row_core=sorted(upper[0]);core=[(row_core[0][0]+i*step,row_core[0][1]) for i in range(10)]
    else:
        first=next((sorted(g) for g in upper if len(g)==3),None);second=next((sorted(g) for g in upper if len(g)==2),None)
        if not first or not second:raise RecognitionError('未能完整定位核心盟约，请截入全部盟约图标')
        dx=float(np.median(np.diff([p[0] for p in first])));x0=first[0][0];y0=float(np.median([p[1] for p in first]));y1=float(np.median([p[1] for p in second]))
        core=[(x0+i*dx,y0) for i in range(3)]+[(x0+(i+.5)*dx,y1) for i in range(2)]+[(x0+(4.3+i)*dx,y0) for i in range(3)]+[(x0+(4.8+i)*dx,y1) for i in range(2)]
    small=[(left+i*step,ys) for i in range(10)]+[(left+i*step,bottom) for i in range(6)]
    height,width=image.shape[:2];margin=d*.29
    if any(x-margin<0 or y-margin<0 or x+margin>=width or y+margin>=height for x,y in core+small):raise RecognitionError('部分盟约图标被截断，请重新截图')
    return core,small,d

def _state(image,x,y,d):
    radius=max(3,round(d*.30));x,y=round(x),round(y);crop=image[y-radius:y+radius,x-radius:x+radius]
    if not crop.size:raise RecognitionError('盟约图标位置不完整')
    hsv=cv2.cvtColor(crop,cv2.COLOR_BGR2HSV);green=(hsv[:,:,0]>=65)&(hsv[:,:,0]<=100)&(hsv[:,:,1]>100)&(hsv[:,:,2]>70)
    amount=float(green.mean())
    if .05<amount<.18:raise RecognitionError('盟约颜色不清晰或被遮挡')
    return 'available' if amount>=.18 else 'banned'

def _classify(image,x,y,d,state,category,shapes,screenshot):
    height,width=image.shape[:2];x,y=round(x),round(y);radius=max(2,int(d*.34));crop=image[max(y-radius,0):min(y+radius,height),max(x-radius,0):min(x+radius,width)]
    gray=cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY);mask=((gray<58) if state=='available' else (gray>135)).astype(np.uint8)*255;observed=_normalize(mask);scores={}
    for name,(kind,expected) in shapes.items():
        if kind!=category:continue
        overlap=np.logical_and(observed,expected).sum();scores[name]=float(2*overlap/max(1,observed.sum()+expected.sum()))
    radius=max(2,round(d*.25));crop=image[y-radius:y+radius,x-radius:x+radius]
    if crop.size:
        target=cv2.resize(crop,(40,40));gray=cv2.cvtColor(target,cv2.COLOR_BGR2GRAY);hsv=cv2.cvtColor(target,cv2.COLOR_BGR2HSV);uncertain=(hsv[:,:,1]<65)&(gray>160) if state=='available' else np.zeros((40,40),bool);test=gray<70 if state=='available' else gray>135
        for item,reference in screenshot:
            if item.get('state')!=state or item.get('kind')!=('core' if category=='核心盟约' else 'small') or item.get('name') not in scores:continue
            refgray=cv2.cvtColor(reference,cv2.COLOR_BGR2GRAY);expected=refgray<70 if state=='available' else refgray>135;valid=~uncertain
            overlap=(test&expected&valid).sum();value=float(2*overlap/max(1,(test&valid).sum()+(expected&valid).sum()));scores[item['name']]=max(scores[item['name']],value)
    ranked=sorted(scores.items(),key=lambda p:p[1],reverse=True)
    if len(ranked)<2:raise RecognitionError('盟约样本不足')
    best,margin=ranked[0][1],ranked[0][1]-ranked[1][1]
    if not ((best>=.64 and margin>=.055) or (best>=.55 and margin>=.15)):raise RecognitionError('有盟约图标被遮挡或识别不确定，请重新截图')
    return ranked[0]

def _legacy_match(original,shapes,templates):
    height,width=original.shape[:2]
    if abs(width/height-1597/857)>.04:raise RecognitionError('图标识别不确定，请重新截图')
    image=cv2.resize(original,(1597,857));result=[]
    core=[(224,215),(338,215),(450,215),(280,365),(394,365),(712,215),(826,215),(940,215),(768,365),(882,365)]
    small=[(139+98*i,605) for i in range(10)]+[(139+98*i,770) for i in range(6)]
    for kind,points in [('core',core),('small',small)]:
        for x,y in points:
            radius=55;area=image[max(0,y-radius):min(857,y+radius),max(0,x-radius):min(1597,x+radius)];scores={}
            for item,pattern in templates:
                if item.get('kind')!=kind or area.shape[0]<pattern.shape[0] or area.shape[1]<pattern.shape[1]:continue
                key=(item['name'],item['state']);score=float(cv2.matchTemplate(area,pattern,cv2.TM_CCOEFF_NORMED).max());scores[key]=max(score,scores.get(key,-1))
            ranked=sorted(scores.items(),key=lambda item:item[1],reverse=True)
            if len(ranked)<2 or ranked[0][1]<.65 or ranked[0][1]-ranked[1][1]<.025:raise RecognitionError('有盟约图标被遮挡或识别不确定，请重新截图')
            (name,state),score=ranked[0];result.append((name,state,score))
    if len(result)!=len(shapes) or {name for name,_,_ in result}!=set(shapes):raise RecognitionError('盟约识别结果有重复或缺失，请重新截图')
    return result

def recognize(path,season_dir):
    try:image=cv2.imdecode(np.fromfile(str(path),dtype=np.uint8),cv2.IMREAD_COLOR)
    except (OSError,ValueError) as error:raise RecognitionError('无法读取图片') from error
    if image is None:raise RecognitionError('无法读取图片')
    h,w=image.shape[:2]
    if w<400 or h<220:raise RecognitionError('截图太小，请上传更清晰的截图')
    original=image;factor=min(2.,max(.5,1400/w));image=cv2.resize(image,None,fx=factor,fy=factor,interpolation=cv2.INTER_AREA if factor<1 else cv2.INTER_CUBIC)
    root=Path(season_dir);database=root/'season.sqlite3'
    try:shapes,screenshot=_assets(str(root.resolve()),database.stat().st_mtime_ns)
    except (OSError,sqlite3.Error) as error:raise RecognitionError('无法读取当前赛季盟约数据') from error
    try:
        core,small,d=_locate(image);result=[]
        for category,points in [('核心盟约',core),('附加盟约',small)]:
            for x,y in points:
                state=_state(image,x,y,d);name,score=_classify(image,x,y,d,state,category,shapes,screenshot);result.append((name,state,score))
        names=[name for name,_,_ in result]
        if len(names)!=len(shapes) or set(names)!=set(shapes):raise RecognitionError('盟约识别结果有重复或缺失，请重新截图')
    except RecognitionError as error:
        try:result=_legacy_match(original,shapes,screenshot)
        except RecognitionError:raise error
    return {'banned':{name for name,state,_ in result if state=='banned'},'available':{name for name,state,_ in result if state=='available'},'scores':result}
