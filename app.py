import json, math, random, re, sqlite3, sys, tempfile, threading, tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog, messagebox, font as tkfont

if sys.platform=='win32':
    try:
        import ctypes
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError,OSError):
        pass

BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE/'.vendor'))
from PIL import Image, ImageDraw, ImageFont, ImageGrab, ImageTk

class Season:
    def __init__(self,path):
        self.path=Path(path); self.db=sqlite3.connect(self.path/'season.sqlite3'); self.db.row_factory=sqlite3.Row; self._images={}
        self.bonds=[dict(r) for r in self.db.execute('select * from bonds')]
        self.operators=[]
        for r in self.db.execute('select * from operators'):
            d=dict(r); d['names']=json.loads(d['names_json']); d['bonds']=[x[0] for x in self.db.execute('select bond_name from operator_bonds where operator_id=?',(d['id'],))]; self.operators.append(d)
        self.image_paths={r[0]:self.path/r[1] for r in self.db.execute("select url,path from images where status='ok'")}
        try:self.trait_icons=dict(self.db.execute('select trait_type,icon_url from trait_icons').fetchall())
        except sqlite3.OperationalError:self.trait_icons={}
    def image(self,url,size):
        try:
            key=(url,size)
            if key not in self._images:
                image=Image.open(self.image_paths[url]).convert('RGBA'); image.thumbnail(size,Image.Resampling.LANCZOS); self._images[key]=ImageTk.PhotoImage(image)
            return self._images[key]
        except (KeyError,OSError): return None
    def bond_icon(self,url,size=28,disabled=False):
        key=('bond',url,size,disabled)
        if key in self._images:return self._images[key]
        try:
            scale=4;dim=size*scale;symbol=Image.open(self.image_paths[url]).convert('RGBA');alpha=symbol.getchannel('A');bounds=alpha.getbbox()
            if not bounds:return None
            alpha=alpha.crop(bounds);limit=int(dim*.70);ratio=min(limit/alpha.width,limit/alpha.height);alpha=alpha.resize((max(1,round(alpha.width*ratio)),max(1,round(alpha.height*ratio))),Image.Resampling.LANCZOS)
            canvas=Image.new('RGBA',(dim,dim),(0,0,0,0));draw=ImageDraw.Draw(canvas)
            draw.ellipse((1,1,dim-2,dim-2),fill=('#c3c9c7' if disabled else '#087c65'))
            draw.ellipse((dim*.09,dim*.09,dim*.91,dim*.91),fill=('#d8dcdb' if disabled else '#10bd98'))
            draw.ellipse((dim*.16,dim*.16,dim*.84,dim*.84),fill=('#e1e4e3' if disabled else '#42eac2'))
            ink=Image.new('RGBA',alpha.size,('#666d6b' if disabled else '#052a23'));canvas.paste(ink,((dim-alpha.width)//2,(dim-alpha.height)//2),alpha)
            self._images[key]=ImageTk.PhotoImage(canvas.resize((size,size),Image.Resampling.LANCZOS));return self._images[key]
        except (KeyError,OSError):return None

class Chip(tk.Canvas):
    """A compact, keyboard-accessible rounded filter control."""
    def __init__(self,parent,text,command,selected=False,icon=None,width=112,disabled=False):
        super().__init__(parent,width=width,height=36,bg='#ffffff',highlightthickness=0,bd=0,takefocus=True,cursor='hand2' if not disabled else 'arrow')
        self.label=text;self.command=command;self.selected=selected;self.icon=icon;self.disabled=disabled;self.w=width
        self.paint();self.bind('<Button-1>',self.activate);self.bind('<Return>',self.activate);self.bind('<space>',self.activate)
    def paint(self):
        self.delete('all');fill='#e3f3ee' if self.selected else '#f2f3f4';fg='#137d68' if self.selected else ('#aaaaaa' if self.disabled else '#33383a');w=self.w
        self.create_polygon(12,2,w-12,2,w-2,2,w-2,12,w-2,24,w-2,34,w-12,34,12,34,2,34,2,24,2,12,2,2,smooth=True,fill=fill,outline='')
        if self.icon:self.create_image(19,18,image=self.icon);self.create_text(37,18,text=self.label,anchor='w',fill=fg,font=('Noto Sans SC',10,'bold' if self.selected else 'normal'))
        else:self.create_text(w/2,18,text=self.label,fill=fg,font=('Noto Sans SC',10,'bold' if self.selected else 'normal'))
    def activate(self,event=None):
        if not self.disabled:self.command()

class RoundedScrollbar(tk.Canvas):
    def __init__(self,parent,command):
        super().__init__(parent,width=14,highlightthickness=0,bd=0,bg='#ffffff',cursor='arrow')
        self.command=command;self.first=0.;self.last=1.;self.drag_offset=None
        self.bind('<Configure>',lambda e:self.paint());self.bind('<Button-1>',self.press);self.bind('<B1-Motion>',self.drag);self.bind('<ButtonRelease-1>',lambda e:setattr(self,'drag_offset',None))
    def set(self,first,last):
        self.first=max(0.,float(first));self.last=min(1.,float(last));self.paint()
    def bounds(self):
        height=max(1,self.winfo_height());thumb=min(height,max(30,(self.last-self.first)*height));top=self.first*max(0,height-thumb)/max(1e-9,1-(self.last-self.first));return top,thumb
    def paint(self):
        self.delete('all')
        if self.last-self.first>=.999:return
        y,h=self.bounds();self.create_polygon(3,y+5,3,y,7,y,11,y,11,y+5,11,y+h-5,11,y+h,7,y+h,3,y+h,3,y+h-5,smooth=True,fill='#a9acab',outline='')
    def press(self,event):
        if self.last-self.first>=.999:return
        y,h=self.bounds()
        if y<=event.y<=y+h:self.drag_offset=event.y-y
        else:self.command('scroll',-1 if event.y<y else 1,'pages')
    def drag(self,event):
        if self.drag_offset is None:return
        _,thumb=self.bounds();available=max(1,self.winfo_height()-thumb);fraction=max(0.,min(1.,(event.y-self.drag_offset)/available));self.command('moveto',fraction*max(0.,1-(self.last-self.first)))

class CollapsibleSection(ttk.Frame):
    def __init__(self,parent,title):
        super().__init__(parent,padding=(6,5));self.title=title;self.expanded=False;self.on_expand=None
        self.button=ttk.Button(self,text='▸  '+title,command=self.toggle);self.button.pack(fill='x')
        self.content=ttk.Frame(self,padding=(4,6,4,4))
    def toggle(self):
        self.expanded=not self.expanded
        if self.expanded:
            if self.on_expand:
                callback=self.on_expand;self.on_expand=None;callback()
            self.content.pack(fill='x');self.button.configure(text='▾  '+self.title)
        else:self.content.pack_forget();self.button.configure(text='▸  '+self.title)

class InfoBadge(tk.Canvas):
    def __init__(self,parent,text,background='#edf3f0',foreground='#31554a',icon=None):
        font=tkfont.Font(family='Noto Sans SC',size=9);width=font.measure(text)+(46 if icon else 28)
        super().__init__(parent,width=width,height=34,bg=parent.cget('bg'),highlightthickness=0,bd=0)
        self.icon=icon;self.create_polygon(10,1,width-10,1,width-1,1,width-1,10,width-1,24,width-1,33,width-10,33,10,33,1,33,1,24,1,10,1,1,smooth=True,fill=background,outline='#e8edeb')
        if icon:self.create_image(18,17,image=icon);self.create_text(39,17,text=text,anchor='w',font=font,fill=foreground)
        else:self.create_text(width/2,17,text=text,font=font,fill=foreground)
        self.font_ref=font

class EffectBox(tk.Canvas):
    def __init__(self,parent,text,background='#f1f3f3',foreground='#414747'):
        super().__init__(parent,bg=parent.cget('bg'),highlightthickness=0,bd=0,height=44)
        self.background=background;self.label=tk.Label(self,text=text,bg=background,fg=foreground,justify='left',anchor='w',font=('Noto Sans SC',9),padx=9,pady=7)
        self.item=self.create_window(6,3,window=self.label,anchor='nw');self.bind('<Configure>',self.relayout)
    def relayout(self,event):
        width=max(120,event.width);self.label.configure(wraplength=max(80,width-30));self.itemconfigure(self.item,width=width-12)
        height=self.label.winfo_reqheight()+6
        if self.winfo_height()!=height:self.configure(height=height)
        self.delete('background');self.create_polygon(9,1,width-9,1,width-1,1,width-1,9,width-1,height-9,width-1,height-1,width-9,height-1,9,height-1,1,height-1,1,height-9,1,9,1,1,smooth=True,fill=self.background,outline='',tags='background');self.tag_lower('background')

class RoundedCard(tk.Canvas):
    def __init__(self,parent,background):
        super().__init__(parent,bg='#ffffff',highlightthickness=0,bd=0,width=500,height=180)
        self.background=background;self.content=tk.Frame(self,bg=background,padx=15,pady=14);self.window=self.create_window(1,1,window=self.content,anchor='nw')
        self.bind('<Configure>',self.relayout);self.content.bind('<Configure>',self.relayout)
    def relayout(self,event=None):
        width=max(120,self.winfo_width());self.itemconfigure(self.window,width=width-2);height=self.content.winfo_reqheight()+2
        if height!=int(float(self.cget('height'))):self.configure(height=height)
        self.delete('card');self.create_polygon(14,1,width-14,1,width-1,1,width-1,14,width-1,height-14,width-1,height-1,width-14,height-1,14,height-1,1,height-1,1,height-14,1,14,1,1,smooth=True,fill=self.background,outline='#e9eded',tags='card');self.tag_lower('card')

class OperatorCard(tk.Canvas):
    """Draw a card in one canvas, avoiding dozens of child widgets per row."""
    def __init__(self,parent,app,op,unavailable,partial):
        super().__init__(parent,bg='#ffffff',highlightthickness=0,bd=0,width=500,height=180)
        self.app=app;self.op=op;self.unavailable=unavailable;self.partial=partial;self._drawn_width=0;self.images=[]
        self.bind('<Configure>',self.relayout)
    def rounded(self,x,y,w,h,fill,outline=''):
        r=9;return self.create_polygon(x+r,y,x+w-r,y,x+w,y,x+w,y+r,x+w,y+h-r,x+w,y+h,x+w-r,y+h,x+r,y+h,x,y+h,x,y+h-r,x,y+r,x,y,smooth=True,fill=fill,outline=outline)
    def relayout(self,event):
        width=event.width
        if width<150 or width==self._drawn_width:return
        self._drawn_width=width;self.delete('all');self.images=[];app=self.app;op=self.op;fonts=app.card_fonts
        bg='#eceff1' if self.unavailable else ('#e9f6ef' if any(app.filters.values()) and not self.partial else '#f3f5f7')
        foreground='#82898c' if self.unavailable else '#242a2d';left=112;right=width-16;content_width=max(80,right-left);y=14
        avatar=app.season.image(op['names'][0]['avatar_url'],(76,76))
        if avatar and self.unavailable:
            try:
                key=('grey-avatar',op['names'][0]['avatar_url'])
                if key not in app.season._images:
                    raw=Image.open(app.season.image_paths[op['names'][0]['avatar_url']]).convert('L').convert('RGBA');raw.thumbnail((76,76));app.season._images[key]=ImageTk.PhotoImage(raw)
                avatar=app.season._images[key]
            except OSError:pass
        if avatar:self.images.append(avatar);self.create_image(19,19,image=avatar,anchor='nw')
        self.create_text(left,y,text=op['names'][0]['name'].replace('(卫戍协议)',''),anchor='nw',font=fonts['title'],fill=foreground);y+=31
        if len(op['names'])>1:
            alias=' / '.join(n['name'].replace('(卫戍协议)','') for n in op['names'][1:]);item=self.create_text(left,y,text='原型：'+alias,anchor='nw',font=fonts['small'],fill='#737e82',width=content_width);y=self.bbox(item)[3]+5
        tier_colors={'Ⅰ':('#e4e9ec','#52616a'),'Ⅱ':('#e3ebf1','#4d7084'),'Ⅲ':('#d4f1df','#147b48'),'Ⅳ':('#d8f2f6','#087f91'),'Ⅴ':('#fcedbf','#936900'),'Ⅵ':('#ffdfc9','#aa4e12')};tierbg,tierfg=tier_colors.get(op['tier'],('#e3e6e7','#444444'))
        badges=[(op['tier']+' 阶',tierbg,tierfg,None)]
        for name in op['bonds']:
            bond=next((b for b in app.season.bonds if b['name']==name),None);icon=app.season.bond_icon(bond['icon_url'],28,disabled=app.banned is not None and name in app.banned) if bond else None
            badges.append((name,'#e4ece8','#33564b',icon))
        x=left
        for index,(text,fill,color,icon) in enumerate(badges):
            bw=fonts['badge'].measure(text)+(45 if icon else 26)
            if x+bw>right and x>left:x=left;y+=40
            before=set(self.find_all());self.rounded(x,y,bw,32,fill,'#d6dedb')
            if icon:self.images.append(icon);self.create_image(x+16,y+16,image=icon);self.create_text(x+34,y+16,text=text,font=fonts['badge'],fill=color,anchor='w')
            else:self.create_text(x+bw/2,y+16,text=text,font=fonts['badge'],fill=color)
            if index>0:
                tag='bond-hover-'+str(index)
                for obj in set(self.find_all())-before:self.addtag_withtag(tag,obj)
                rect=(x,y,bw,32);self.tag_bind(tag,'<Enter>',lambda event,n=text,r=rect:app.start_bond_hover(self,n,r));self.tag_bind(tag,'<Leave>',lambda event:app.schedule_bond_hover_close())
            x+=bw+7
        y+=40;trait=op['trait_type'];icon=app.season.image(app.season.trait_icons.get(trait,''),(18,18));bw=fonts['badge'].measure(trait)+(40 if icon else 24)
        self.rounded(left,y,bw,30,'#7b8583')
        if icon:self.images.append(icon);self.create_image(left+14,y+15,image=icon);self.create_text(left+28,y+15,text=trait,font=fonts['badge'],fill='white',anchor='w')
        else:self.create_text(left+bw/2,y+15,text=trait,font=fonts['badge'],fill='white')
        if app.banned is not None:self.create_text(left+bw+10,y+15,text=app.status(op),font=fonts['small'],fill='#878f90' if self.unavailable else '#168256',anchor='w')
        y+=39
        for text,fill,color in [(op['trait_normal'],'#e5eaec',foreground)]+([('精锐：'+op['trait_elite'],'#dfeee7','#35634f' if not self.unavailable else '#82898c')] if op['trait_elite'] else []):
            item=self.create_text(left+10,y+8,text=text,anchor='nw',width=max(60,content_width-20),font=fonts['body'],fill=color);bbox=self.bbox(item);height=max(36,bbox[3]-y+8);rect=self.rounded(left,y,content_width,height,fill);self.tag_lower(rect,item);y+=height+8
        height=max(112,y+8);outer=self.rounded(1,1,width-2,height-2,bg,'#bfcad0');self.tag_lower(outer)
        if int(float(self.cget('height')))!=height:self.configure(height=height)

class CompactOperatorCard(tk.Canvas):
    """Uniform home-page card; all details remain available on hover."""
    def __init__(self,parent,app,op):
        super().__init__(parent,width=305,height=122,bg='#ffffff',highlightthickness=0,bd=0)
        self.app=app;self.op=op;self.images=[];self.paint()
        self.bind('<Enter>',lambda e:app.start_operator_hover(self,op));self.bind('<Leave>',lambda e:app.schedule_operator_hover_close())
    def paint(self):
        self.delete('all');app=self.app;op=self.op;unavailable=app.status(op)=='不可用';bg='#e7eaeb' if unavailable else '#f3f6f5';fg='#969e9f' if unavailable else '#25302d'
        self.create_polygon(10,1,295,1,304,1,304,10,304,112,304,121,295,121,10,121,1,121,1,112,1,10,1,1,smooth=True,fill=bg,outline='#cbd4d4')
        def rounded(x,y,w,h,fill,outline=''):
            r=7;return self.create_polygon(x+r,y,x+w-r,y,x+w,y,x+w,y+r,x+w,y+h-r,x+w,y+h,x+w-r,y+h,x+r,y+h,x,y+h,x,y+h-r,x,y+r,x,y,smooth=True,fill=fill,outline=outline)
        url=op['names'][0]['avatar_url'];im=app.season.image(url,(58,58))
        if im and unavailable:
            try:
                key=('small-grey',url)
                if key not in app.season._images:
                    raw=Image.open(app.season.image_paths[url]).convert('L').convert('RGBA');raw.thumbnail((58,58));app.season._images[key]=ImageTk.PhotoImage(raw)
                im=app.season._images[key]
            except OSError:pass
        if im:self.images.append(im);self.create_image(9,13,image=im,anchor='nw')
        name=op['names'][0]['name'].replace('(卫戍协议)','');trait=op['trait_type'];status='已 Ban' if unavailable else ('可用' if app.banned is not None else '')
        small=app.card_fonts['small'];trait_width=small.measure(trait)+12;status_width=small.measure(status)+12 if status else 0;space=5;limit=max(35,221-trait_width-status_width-2*space)
        namefont=tkfont.Font(family='Noto Sans SC',size=12,weight='bold')
        while namefont.measure(name)>limit and int(namefont.cget('size'))>7:namefont.configure(size=int(namefont.cget('size'))-1)
        self.namefont=namefont;self.create_text(76,12,text=name,font=namefont,fill=fg,anchor='nw');x=76+namefont.measure(name)+space
        if trait:
            trait_bg='#d3d8d8' if unavailable else ('#e99a42' if trait=='持续叠加' else '#8a9592');rounded(x,11,trait_width,24,trait_bg);self.create_text(x+trait_width/2,23,text=trait,font=small,fill='#a3aaaa' if unavailable else '#ffffff');x+=trait_width+space
        if status:
            rounded(x,11,status_width,24,'#d3d8d8' if unavailable else '#d9f0e4');self.create_text(x+status_width/2,23,text=status,font=small,fill='#a3aaaa' if unavailable else '#138454')
        tierbg={'Ⅰ':'#dfe5e7','Ⅱ':'#dbe7ee','Ⅲ':'#cfead9','Ⅳ':'#d1ecf2','Ⅴ':'#f7e7b7','Ⅵ':'#f8dac5'}.get(op['tier'],'#e6e6e6')
        x,y=76,43;rounded(x,y,34,25,'#d2d6d6' if unavailable else tierbg,'#d2dada');self.create_text(x+17,y+12,text=op['tier']+'阶',font=('Noto Sans SC',8),fill=fg);x+=40
        for name in op['bonds']:
            bond=next((b for b in app.season.bonds if b['name']==name),None);icon=app.season.bond_icon(bond['icon_url'],20,disabled=unavailable or (app.banned is not None and name in app.banned)) if bond else None
            text_width=app.card_fonts['small'].measure(name);span=25+text_width+7
            if x+span>296:x=76;y+=27
            rounded(x,y,span,25,'#d8dddd' if unavailable else '#e4eeea','#d2dada')
            if icon:self.images.append(icon);self.create_image(x+12,y+12,image=icon)
            self.create_text(x+24,y+12,text=name,font=app.card_fonts['small'],fill=fg,anchor='w');x+=span+4

class RelationshipGraph(tk.Canvas):
    """Supersampled circular relationship graph with interactive emphasis."""
    def __init__(self,parent,app,center,nodes,edges):
        super().__init__(parent,height=850,bg='#f5f7f8',highlightthickness=1,highlightbackground='#cbd4d8',bd=0,cursor='hand2')
        self.app=app;self.center=center;self.nodes=nodes[:];self.original_nodes=nodes[:];self.edges=edges;self.focus=None;self.positions={};self.hit_edges=[];self.hit_labels=[];self.redraw_job=None;self.zoom=1.;self.base_width=None
        self.bind('<Configure>',self.schedule_draw);self.bind('<Button-1>',self.clicked)
    def schedule_draw(self,event=None):
        if self.redraw_job:self.after_cancel(self.redraw_job)
        self.redraw_job=self.after(80,self.draw_graph)
    def active(self,edge):
        if not any(self.app.status(op)!='不可用' for op in edge['ops']):return False
        if self.focus is None:return True
        kind,value=self.focus
        if kind=='node':return value in (edge['a'],edge['b'])
        return edge['kind']==kind
    def draw_graph(self,attempt=0):
        self.redraw_job=None
        if not self.winfo_exists():return
        width=max(300,self.base_width or self.winfo_width());height=850;scale=2;image=Image.new('RGB',(width*scale,height*scale),'#f5f7f8');draw=ImageDraw.Draw(image,'RGBA')
        try:
            path='C:/Windows/Fonts/NotoSansSC-VF.ttf';font=ImageFont.truetype(path,16*scale);nodefont=ImageFont.truetype(path,19*scale);nodefont_small=ImageFont.truetype(path,16*scale);titlefont=ImageFont.truetype(path,20*scale)
        except OSError:
            path='C:/Windows/Fonts/msyh.ttc';font=ImageFont.truetype(path,16*scale);nodefont=ImageFont.truetype(path,19*scale);nodefont_small=ImageFont.truetype(path,16*scale);titlefont=ImageFont.truetype(path,20*scale)
        cx=width/2;cy=height/2-40;radius=min(305,(width-160)/2);positions={self.center:(cx,cy)}
        for i,name in enumerate(self.nodes):
            angle=2*math.pi*i/max(1,len(self.nodes))-math.pi/2;positions[name]=(cx+radius*math.cos(angle),cy+radius*math.sin(angle))
        self.positions=positions;self.hit_edges=[];self.hit_labels=[];pending=[]
        def rect(coords):return tuple(round(z*scale) for z in coords)
        for edge in self.edges:
            if edge['a'] not in positions or edge['b'] not in positions:continue
            x1,y1=positions[edge['a']];x2,y2=positions[edge['b']];highlight=self.active(edge);color=('#82a2b2' if edge['kind']=='core' else '#dd8444') if highlight else '#dce2e4'
            draw.line(rect((x1,y1,x2,y2)),fill=color,width=3*scale);self.hit_edges.append((x1,y1,x2,y2,edge))
            labels=[(op['names'][0]['name'].replace('(卫戍协议)','')+' · '+op['tier'],highlight and self.app.status(op)!='不可用') for op in edge['ops']]
            pending.append((edge,labels,x1,y1,x2,y2))
        occupied=[]
        for name,(x,y) in positions.items():
            r=(46 if name==self.center else 37)+8;occupied.append((x-r,y-r,x+r,y+r))
        def overlaps(a,b):return a[0]<b[2]+4 and a[2]+4>b[0] and a[1]<b[3]+4 and a[3]+4>b[1]
        groups=[]
        for edge,labels,x1,y1,x2,y2 in pending:
            sizes=[draw.textbbox((0,0),label,font=font) for label,_ in labels];half_w=max((b[2]-b[0])/scale for b in sizes)/2+7;line_height=23;half_h=(line_height*len(labels)+8)/2
            choices=[]
            for step in sorted(range(5,96,2),key=lambda v:abs(v-50)):
                t=step/100;x=x1+(x2-x1)*t;y=y1+(y2-y1)*t;b=(x-half_w,y-half_h,x+half_w,y+half_h)
                if b[0]>=4 and b[1]>=4 and b[2]<=width-4 and b[3]<=height-105 and not any(overlaps(b,node) for node in occupied):choices.append((x,y,b))
            groups.append({'edge':edge,'labels':labels,'choices':choices,'half_h':half_h,'half_w':half_w,'line_height':line_height,'ends':(x1,y1,x2,y2)})
        groups.sort(key=lambda group:(len(group['choices']),-len(group['labels'])))
        placed=[];budget=[160000]
        def arrange(index):
            if index==len(groups):return True
            if budget[0]<=0:return False
            budget[0]-=1
            for option in groups[index]['choices']:
                if any(overlaps(option[2],old[1][2]) for old in placed):continue
                placed.append((groups[index],option))
                if arrange(index+1):return True
                placed.pop()
            return False
        if not arrange(0):
            placed=[]
            for group in groups:
                choice=next((c for c in group['choices'] if not any(overlaps(c[2],old[1][2]) for old in placed)),None)
                if choice is None:
                    choices=group['choices'];choice=min(choices,key=lambda c:sum(overlaps(c[2],old[1][2]) for old in placed)) if choices else None
                if choice:placed.append((group,choice))
        imperfect=len(placed)!=len(groups) or any(overlaps(a[1][2],b[1][2]) for i,a in enumerate(placed) for b in placed[i+1:])
        if imperfect and attempt<8:
            self.nodes=self.original_nodes[:];random.Random(attempt).shuffle(self.nodes);return self.draw_graph(attempt+1)
        for group,(x,y,bounds) in placed:
            edge=group['edge'];has_active=any(active for _,active in group['labels']);outline=('#a1bdc9' if edge['kind']=='core' else '#dfa77f') if has_active else '#dce3e4'
            draw.rounded_rectangle(rect(bounds),radius=5*scale,fill=(255,255,255,225),outline=outline,width=scale)
            for i,(label,active) in enumerate(group['labels']):
                ty=bounds[1]+4+group['line_height']*(i+.5);draw.text((round(x*scale),round(ty*scale)),label,font=font,fill='#506267' if active else '#c6cecf',anchor='mm')
            self.hit_labels.append((bounds,edge))
        for i,name in enumerate([self.center]+self.nodes):
            x,y=positions[name];r=46 if name==self.center else 37
            fill='#2998b4' if name==self.center else '#0f9f71'
            if self.app.banned is not None and name in self.app.banned:fill='#aeb9b9'
            draw.ellipse(rect((x-r-2,y-r-2,x+r+2,y+r+2)),fill='#d8dfdf');draw.ellipse(rect((x-r,y-r,x+r,y+r)),fill=fill,outline='#ffffff',width=2*scale)
            draw.text((round(x*scale),round(y*scale)),name,font=titlefont if name==self.center else (nodefont_small if len(name)>3 else nodefont),fill='#ffffff',anchor='mm')
        draw.line(rect((20,height-78,80,height-78)),fill='#82a2b2',width=3*scale);draw.text(rect((90,height-78)),'主盟约与副盟约',font=font,fill='#617075',anchor='lm')
        draw.line(rect((20,height-50,80,height-50)),fill='#dd8444',width=3*scale);draw.text(rect((90,height-50)),'副盟约之间',font=font,fill='#617075',anchor='lm')
        draw.text(rect((20,height-21)),'点击盟约或连线高亮，点击空白处恢复',font=font,fill='#7b888b',anchor='lm')
        self.photo=ImageTk.PhotoImage(image.resize((round(width*self.zoom),round(height*self.zoom)),Image.Resampling.LANCZOS));self.delete('all');self.create_image(0,0,image=self.photo,anchor='nw')
    def clicked(self,event):
        x,y=event.x/self.zoom,event.y/self.zoom;selection=None
        for name,(nx,ny) in self.positions.items():
            if math.hypot(x-nx,y-ny)<(46 if name==self.center else 37):selection=('node',name);break
        if selection is None:
            for (x1,y1,x2,y2),edge in reversed(self.hit_labels):
                if x1<=x<=x2 and y1<=y<=y2:selection=(edge['kind'],None);break
        if selection is None:
            best=9.
            for x1,y1,x2,y2,edge in self.hit_edges:
                dx=x2-x1;dy=y2-y1;length=dx*dx+dy*dy;t=max(0.,min(1.,((x-x1)*dx+(y-y1)*dy)/length)) if length else 0.;distance=math.hypot(x-(x1+t*dx),y-(y1+t*dy))
                if distance<best:best=distance;selection=(edge['kind'],None)
        self.focus=None if selection==self.focus else selection;self.draw_graph()

class RichEffect(tk.Text):
    """Read-only text with highlighted numbers and automatic wrapped height."""
    def __init__(self,parent,text,bg='#f0f4f6'):
        super().__init__(parent,bg=bg,fg='#313a3d',font=('Noto Sans SC',10),bd=0,highlightthickness=0,wrap='char',padx=10,pady=8,cursor='arrow',height=1,width=10)
        self.tag_configure('number',foreground='#168bd0')
        self.tag_configure('action',foreground='#0c9a78')
        last=0
        for match in re.finditer(r'[+−-]?\d+(?:\.\d+)?%?',text):
            self.insert('end',text[last:match.start()]);self.insert('end',match.group(),'number');last=match.end()
        self.insert('end',text[last:])
        for match in re.finditer(r'(?:被动效果|拖拽使用|点击使用)(?:（消耗\d+）)?[：:]?',text):
            self.tag_add('action',f'1.0+{match.start()}c',f'1.0+{match.end()}c')
        self.tag_raise('number');self.configure(state='disabled');self.bind('<Configure>',self.reheight)
    def reheight(self,event=None):
        try:
            count=self.count('1.0','end-1c','displaylines');lines=max(1,(count[0] if count else 0)+1)
            if int(self.cget('height'))!=lines:self.configure(height=lines)
        except tk.TclError:pass

def alliance_effect_sections(text):
    """Split at explicit on-field operator counts without inventing thresholds."""
    activation=re.match(r'^激活所需人数\s*(\d+)',text)
    count=activation.group(1) if activation else None
    rest=text[activation.end():] if activation else text
    parts=[part.strip() for part in re.split(r'(?=<在场[^>]*\d+\s*名[^>]*>|<每叠加[^>]*\d+\s*层[^>]*>)',rest) if part.strip()]
    return count,parts

def format_strategy_details(text):
    text=re.sub(r'^(初始生命值\s*\d+)',r'\1\n',text)
    return re.sub(r'(?<!\n)(?=(?:被动效果|拖拽使用|点击使用))','\n',text)

class App(tk.Tk):
    def __init__(self):
        super().__init__(); self.title('卫戍协议助手'); self.geometry('1280x820'); self.minsize(1050,680)
        for name in ('TkDefaultFont','TkTextFont','TkFixedFont','TkMenuFont','TkHeadingFont','TkCaptionFont','TkSmallCaptionFont','TkIconFont','TkTooltipFont'):
            tkfont.nametofont(name).configure(family='Noto Sans SC')
        for name in ('TkDefaultFont','TkTextFont','TkMenuFont'):
            tkfont.nametofont(name).configure(size=11)
        self.option_add('*Font','{Noto Sans SC} 11')
        self.card_fonts={'title':tkfont.Font(family='Noto Sans SC',size=15,weight='bold'),'body':tkfont.Font(family='Noto Sans SC',size=11),'badge':tkfont.Font(family='Noto Sans SC',size=10),'small':tkfont.Font(family='Noto Sans SC',size=10)}
        self.season=Season(BASE/'season-provisional'); self.banned=None; self.enemies=''; self.filters={}; self.pictures=[]
        self.configure(bg='#ffffff'); style=ttk.Style(self); style.theme_use('clam')
        style.configure('.',font=('Noto Sans SC',11),background='#ffffff',foreground='#202123')
        style.configure('TFrame',background='#ffffff'); style.configure('TLabel',background='#ffffff',foreground='#202123')
        style.configure('TButton',background='#f4f4f4',foreground='#202123',borderwidth=0,padding=(14,9)); style.map('TButton',background=[('active','#e8e8e8')])
        style.configure('TEntry',fieldbackground='#f7f7f7',bordercolor='#e5e5e5',padding=7)
        style.configure('TCombobox',fieldbackground='#f7f7f7',bordercolor='#e5e5e5',padding=7)
        style.configure('TLabelframe',background='#ffffff',bordercolor='#e9e9e9',padding=10);style.configure('TLabelframe.Label',background='#ffffff',foreground='#333333',font=('Noto Sans SC',10,'bold'))
        style.configure('Title.TLabel',font=('Noto Sans SC',19,'bold'));style.configure('Card.TFrame',background='#ffffff')
        style.layout('Hidden.TNotebook.Tab',[]);style.configure('Hidden.TNotebook',background='#ffffff',borderwidth=0)
        self._normal_geometry=None;self._maximized=False;self._minimizing=False;self.overrideredirect(True)
        titlebar=tk.Frame(self,bg='#f5f5f3',height=38);titlebar.pack(fill='x',side='top');titlebar.pack_propagate(False)
        title=tk.Label(titlebar,text='卫戍协议助手',bg='#f5f5f3',fg='#777777',font=('Noto Sans SC',9),anchor='w');title.pack(side='left',padx=18,fill='y')
        controls=tk.Frame(titlebar,bg='#f5f5f3');controls.pack(side='right',fill='y')
        for glyph,command,hover in [('—',self.minimize_window,'#e8e8e6'),('□',self.toggle_maximize,'#e8e8e6'),('×',self.destroy,'#e64b56')]:
            button=tk.Button(controls,text=glyph,command=command,bd=0,relief='flat',bg='#f5f5f3',fg='#555555',activebackground=hover,activeforeground='white' if glyph=='×' else '#222222',font=('Noto Sans SC',12),width=4,cursor='hand2');button.pack(side='left',fill='y')
        for widget in (titlebar,title):
            widget.bind('<ButtonPress-1>',self.start_window_drag);widget.bind('<B1-Motion>',self.drag_window);widget.bind('<Double-Button-1>',lambda e:self.toggle_maximize())
        self.bind('<Map>',self.restore_window_frame,add='+')
        shell=tk.Frame(self,bg='#ffffff');shell.pack(fill='both',expand=True)
        sidebar=tk.Frame(shell,bg='#f5f5f3',width=220,padx=14,pady=22);sidebar.pack(side='left',fill='y');sidebar.pack_propagate(False)
        tk.Label(sidebar,text='卫戍协议助手',bg='#f5f5f3',fg='#202123',font=('Noto Sans SC',15,'bold'),anchor='w').pack(fill='x',padx=8)
        tk.Label(sidebar,text='规程  ·  赛季资料',bg='#f5f5f3',fg='#888888',font=('Noto Sans SC',9),anchor='w').pack(fill='x',padx=8,pady=(4,22))
        self.tabs=ttk.Notebook(shell,style='Hidden.TNotebook');self.tabs.pack(side='right',fill='both',expand=True,padx=24,pady=22);self.pages={};self.nav={}
        for title in ('本局主页','干员','盟约','策略','装备'):
            page=ttk.Frame(self.tabs,padding=10); self.tabs.add(page,text=title);self.pages[title]=page
            button=tk.Button(sidebar,text=title,anchor='w',bd=0,relief='flat',cursor='hand2',font=('Noto Sans SC',11),padx=14,pady=10,command=lambda name=title:self.select_page(name));button.pack(fill='x',pady=2);self.nav[title]=button
        tk.Button(sidebar,text='切换赛季数据包',anchor='w',bd=0,relief='flat',bg='#f5f5f3',activebackground='#e8e8e6',fg='#666666',padx=14,pady=10,command=self.change_season).pack(side='bottom',fill='x')
        self.select_page('本局主页')
        self.bind('<Control-v>',self.paste_screenshot)
        self.bind('<Control-V>',self.paste_screenshot)
        self.render_home();self.render_operators();self.render_bonds();self.render_entries('策略');self.render_entries('装备')
        self.resize_grip=ttk.Sizegrip(self);self.resize_grip.place(relx=1,rely=1,anchor='se');self.resize_grip.bind('<ButtonPress-1>',self.start_resize);self.resize_grip.bind('<B1-Motion>',self.resize_window)
        self.resize_edges=[]
        for side,cursor in [('n','size_ns'),('s','size_ns'),('e','size_we'),('w','size_we'),('nw','size_nw_se'),('ne','size_ne_sw'),('sw','size_ne_sw'),('se','size_nw_se')]:
            edge=tk.Frame(self,bg='#ededeb',cursor=cursor);edge.bind('<ButtonPress-1>',lambda e,s=side:self.start_edge_resize(e,s));edge.bind('<B1-Motion>',self.drag_edge_resize);self.resize_edges.append((side,edge))
        self.show_resize_edges()
    def show_resize_edges(self):
        for side,edge in self.resize_edges:
            positions={'n':dict(x=10,y=0,relwidth=1,width=-20,height=5),'s':dict(x=10,rely=1,y=-5,relwidth=1,width=-20,height=5),'w':dict(x=0,y=10,relheight=1,height=-20,width=5),'e':dict(relx=1,x=-5,y=10,relheight=1,height=-20,width=5),'nw':dict(x=0,y=0,width=10,height=10),'ne':dict(relx=1,x=-10,y=0,width=10,height=10),'sw':dict(x=0,rely=1,y=-10,width=10,height=10),'se':dict(relx=1,rely=1,x=-10,y=-10,width=10,height=10)}
            edge.place(**positions[side]);edge.lift()
    def start_edge_resize(self,event,side):
        self._edge_start=(side,event.x_root,event.y_root,self.winfo_x(),self.winfo_y(),self.winfo_width(),self.winfo_height())
    def drag_edge_resize(self,event):
        if self._maximized:return
        side,x,y,left,top,width,height=self._edge_start;dx=event.x_root-x;dy=event.y_root-y
        if 'e' in side:width=max(1050,width+dx)
        if 's' in side:height=max(680,height+dy)
        if 'w' in side:
            new_width=max(1050,width-dx);left+=width-new_width;width=new_width
        if 'n' in side:
            new_height=max(680,height-dy);top+=height-new_height;height=new_height
        self.geometry(f'{width}x{height}{left:+d}{top:+d}')
    def start_window_drag(self,event):
        self._drag_start=(event.x_root,event.y_root,self.winfo_x(),self.winfo_y())
    def drag_window(self,event):
        if self._maximized:return
        x,y,left,top=self._drag_start;self.geometry(f'{left+event.x_root-x:+d}{top+event.y_root-y:+d}')
    def start_resize(self,event):
        self._resize_start=(event.x_root,event.y_root,self.winfo_width(),self.winfo_height())
    def resize_window(self,event):
        if self._maximized:return
        x,y,w,h=self._resize_start;self.geometry(f'{max(1050,w+event.x_root-x)}x{max(680,h+event.y_root-y)}')
    def minimize_window(self):
        self._minimizing=True;self.overrideredirect(False);self.iconify()
    def restore_window_frame(self,event):
        if event.widget is self and self._minimizing and self.state()=='normal':
            self._minimizing=False;self.after_idle(lambda:self.overrideredirect(True))
    def toggle_maximize(self):
        if self._maximized:
            self._maximized=False;self.geometry(self._normal_geometry);self.resize_grip.place(relx=1,rely=1,anchor='se');self.show_resize_edges();return
        self.update_idletasks();self._normal_geometry=self.geometry()
        import ctypes
        from ctypes import wintypes
        class RECT(ctypes.Structure):_fields_=[('left',wintypes.LONG),('top',wintypes.LONG),('right',wintypes.LONG),('bottom',wintypes.LONG)]
        class MONITORINFO(ctypes.Structure):_fields_=[('cbSize',wintypes.DWORD),('rcMonitor',RECT),('rcWork',RECT),('dwFlags',wintypes.DWORD)]
        user32=ctypes.windll.user32;user32.MonitorFromWindow.argtypes=[wintypes.HWND,wintypes.DWORD];user32.MonitorFromWindow.restype=wintypes.HANDLE;user32.GetMonitorInfoW.argtypes=[wintypes.HANDLE,ctypes.POINTER(MONITORINFO)]
        info=MONITORINFO();info.cbSize=ctypes.sizeof(info);monitor=user32.MonitorFromWindow(self.winfo_id(),2)
        if user32.GetMonitorInfoW(monitor,ctypes.byref(info)):
            r=info.rcWork;self.geometry(f'{r.right-r.left}x{r.bottom-r.top}{r.left:+d}{r.top:+d}')
        else:self.geometry(f'{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0')
        self._maximized=True;self.resize_grip.place_forget()
        for _,edge in self.resize_edges:edge.place_forget()
    def select_page(self,name):
        self.close_bond_hover();self.close_operator_hover()
        if name not in ('盟约','策略'):self.close_catalog_hover()
        elif getattr(self,'catalog_popup',None):self.close_catalog_hover()
        if name!='干员' and getattr(self,'filterpopup',None) and self.filterpopup.winfo_exists():
            self.filterpopup.withdraw();self.filter_open=False
        self.tabs.select(self.pages[name])
        for key,button in self.nav.items():
            selected=key==name;button.configure(bg='#e5e5e2' if selected else '#f5f5f3',activebackground='#e5e5e2',fg='#171717')
    def change_season(self):
        folder=filedialog.askdirectory(title='选择包含 season.sqlite3 的数据包目录')
        if not folder:return
        try:
            new=Season(folder); self.season.db.close(); self.season=new;self.banned=None;self.enemies='';self.filters={};self.redraw()
        except Exception as e:messagebox.showerror('数据包加载失败',str(e))
    def clear(self,page):
        for w in page.winfo_children():w.destroy()
    def redraw(self):
        self.close_bond_hover();self.pictures=[];self.render_home();self.render_operators();self.render_bonds();self.render_entries('策略');self.render_entries('装备')
    def scroll(self,parent):
        frame=ttk.Frame(parent);frame.pack(fill='both',expand=True); canvas=tk.Canvas(frame,highlightthickness=0,bg='#ffffff');bar=RoundedScrollbar(frame,command=canvas.yview);canvas.configure(yscrollcommand=bar.set);bar.pack(side='right',fill='y');canvas.pack(side='left',fill='both',expand=True);body=ttk.Frame(canvas);body.scroll_canvas=canvas;body.scrollbar=bar;win=canvas.create_window((0,0),window=body,anchor='nw');body.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')));canvas.bind('<Configure>',lambda e:canvas.itemconfigure(win,width=e.width));canvas.bind('<Enter>',lambda e:canvas.bind_all('<MouseWheel>',lambda ev:canvas.yview_scroll(-int(ev.delta/120),'units')));canvas.bind('<Leave>',lambda e:canvas.unbind_all('<MouseWheel>'));return body
    def status(self,op):
        if self.banned is None:return '未筛选'
        return '不可用' if op['bonds'] and all(b in self.banned for b in op['bonds']) else '可用'
    def render_home(self):
        self.close_graph_window();self.close_operator_hover()
        if getattr(self,'home_hover_job',None):self.after_cancel(self.home_hover_job);self.home_hover_job=None
        p=self.pages['本局主页'];self.clear(p)
        self.home_header=tk.Frame(p,bg='#ffffff',highlightbackground='#e5e8e9',highlightthickness=1);self.home_header.pack(fill='x')
        bar=ttk.Frame(self.home_header,padding=(10,8,50,8));bar.pack(fill='x');ttk.Label(bar,text='本局信息',style='Title.TLabel').pack(side='left');statusbox=tk.Frame(bar,bg='#ffffff');statusbox.pack(side='left',padx=12);InfoBadge(statusbox,'未筛选' if self.banned is None else '本局筛选中',background='#edf0f2' if self.banned is None else '#def3e9',foreground='#627176' if self.banned is None else '#168256').pack();ttk.Button(bar,text='导入本局截图',command=self.screenshot).pack(side='right');ttk.Button(bar,text='读取剪贴板截图',command=self.clipboard_screenshot).pack(side='right');ttk.Button(bar,text='结束本局 / 重置',command=self.reset).pack(side='right');ttk.Button(bar,text='手动设置本局信息',command=self.edit_bans).pack(side='right')
        f=ttk.Frame(self.home_header,padding=(10,0,10,5));f.pack(fill='x');self.home_selector=f;self.home_hover_job=None
        heading=ttk.Frame(f);heading.pack(fill='x');ttk.Label(heading,text='选择大盟约',font=('Noto Sans SC',12,'bold')).pack(side='left',pady=(8,7));self.home_toggle=tk.Canvas(self.home_header,width=30,height=30,bg='#ffffff',highlightthickness=0,bd=0,cursor='hand2');self.home_toggle.create_oval(2,2,28,28,fill='#f0f2f3',outline='#dce1e2');self.home_toggle_arrow=self.home_toggle.create_line(10,12,15,17,20,12,fill='#596668',width=2,capstyle='round',joinstyle='round');self.home_toggle.bind('<Button-1>',lambda e:self.toggle_home_selector());self.core=tk.StringVar();self.corechips={};self.smallchips={};self.selected_small=tk.StringVar();self.home_collapsed=False;self.home_past_top=False
        row=ttk.Frame(f);row.pack(fill='x');values=[b for b in self.season.bonds if b['category']=='核心盟约']
        def choose(name):
            self.core.set(name);self.selected_small.set('')
            for key,chip in self.corechips.items():chip.selected=key==name;chip.paint()
            for chip in self.smallchips.values():chip.selected=False;chip.paint()
            self.show_links()
        for i,b in enumerate(values):
            banned=self.banned is not None and b['name'] in self.banned;icon=self.season.bond_icon(b['icon_url'],28,disabled=banned);chip=Chip(row,b['name'],lambda n=b['name']:choose(n),icon=icon,disabled=banned);chip.grid(row=i//5,column=i%5,padx=(0,6),pady=3,sticky='w');self.corechips[b['name']]=chip;self.bind_bond_hover(chip,b['name'])
        self.home_smallbox=ttk.Frame(f);self.home_smallbox.pack(fill='x');ttk.Label(self.home_smallbox,text='选择小盟约',font=('Noto Sans SC',12,'bold')).pack(anchor='w',pady=(12,7));smallrow=ttk.Frame(self.home_smallbox);smallrow.pack(fill='x')
        def choose_small(name):
            self.selected_small.set(name);self.core.set('')
            for key,chip in self.smallchips.items():chip.selected=key==name;chip.paint()
            for chip in self.corechips.values():chip.selected=False;chip.paint()
            self.show_small_links()
        self.combat_small_names={'精准','迅捷','灵巧','坚守','助力','突袭','不屈','聚合','奥术','协防干员'}
        for i,b in enumerate(x for x in self.season.bonds if x['category']=='附加盟约' and x['name'] in self.combat_small_names):
            banned=self.banned is not None and b['name'] in self.banned;icon=self.season.bond_icon(b['icon_url'],28,disabled=banned);chip=Chip(smallrow,b['name'],lambda n=b['name']:choose_small(n),icon=icon,disabled=banned);chip.grid(row=i//6,column=i%6,padx=(0,6),pady=3,sticky='w');self.smallchips[b['name']]=chip;self.bind_bond_hover(chip,b['name'])
        self.home_header_rule=tk.Frame(self.home_header,bg='#d9dddf',height=1);self.home_header_rule.pack(fill='x',side='bottom');tk.Frame(p,bg='#eceeef',height=3).pack(fill='x')
        self.links=self.scroll(p);ttk.Label(self.links,text='选择盟约，查看相关干员与盟约关系。',foreground='#888888').pack(anchor='w',pady=25)
        def on_scroll(first,last):
            self.links.scrollbar.set(first,last);past=float(first)>0.005
            if past!=self.home_past_top:
                self.home_past_top=past;self.set_home_collapsed(past)
                if past:self.home_toggle.place(relx=1,rely=0,x=-12,y=10,anchor='ne');tk.Misc.tkraise(self.home_toggle)
                else:self.home_toggle.place_forget()
        self.links.scroll_canvas.configure(yscrollcommand=on_scroll)
        def header_wheel(event):
            self.links.scroll_canvas.yview_scroll(-int(event.delta/120),'units');return 'break'
        def bind_wheel(widget):
            widget.bind('<MouseWheel>',header_wheel,add='+')
            widget.bind('<Enter>',self.home_header_enter,add='+');widget.bind('<Leave>',self.schedule_home_hover_close,add='+')
            for child in widget.winfo_children():bind_wheel(child)
        bind_wheel(self.home_header)
    def set_home_collapsed(self,collapsed):
        if self.home_collapsed==collapsed:return
        self.home_collapsed=collapsed
        if collapsed:self.home_selector.pack_forget();self.home_toggle.coords(self.home_toggle_arrow,10,12,15,17,20,12)
        else:self.home_selector.pack(fill='x',before=self.home_header_rule);self.home_toggle.coords(self.home_toggle_arrow,10,17,15,12,20,17)
    def toggle_home_selector(self):
        self.set_home_collapsed(not self.home_collapsed)
    def home_header_enter(self,event=None):
        if self.home_hover_job:self.after_cancel(self.home_hover_job);self.home_hover_job=None
        if self.home_past_top:self.set_home_collapsed(False)
    def schedule_home_hover_close(self,event=None):
        if self.home_hover_job:self.after_cancel(self.home_hover_job)
        self.home_hover_job=self.after(200,self.close_home_if_outside)
    def close_home_if_outside(self):
        self.home_hover_job=None
        if not self.home_past_top or not self.home_header.winfo_exists():return
        x,y=self.winfo_pointerxy()
        def inside(w):return w and w.winfo_exists() and w.winfo_ismapped() and w.winfo_rootx()<=x<w.winfo_rootx()+w.winfo_width() and w.winfo_rooty()<=y<w.winfo_rooty()+w.winfo_height()
        if not inside(self.home_header) and not inside(getattr(self,'bond_popup',None)):self.set_home_collapsed(True)
    def small_intersections(self,name):
        others=[b['name'] for b in self.season.bonds if b['category']=='附加盟约' and b['name'] in self.combat_small_names and b['name']!=name]
        return {other:[o for o in self.season.operators if name in o['bonds'] and other in o['bonds']] for other in others if any(name in o['bonds'] and other in o['bonds'] for o in self.season.operators)}
    def close_operator_hover(self):
        if getattr(self,'operator_hover_job',None):self.after_cancel(self.operator_hover_job);self.operator_hover_job=None
        popup=getattr(self,'operator_popup',None)
        if popup and popup.winfo_exists():popup.destroy()
        self.operator_popup=None;self.operator_hover_anchor=None
    def start_operator_hover(self,widget,op):
        self.close_operator_hover();self.operator_hover_anchor=widget;self.operator_hover_job=self.after(350,lambda:self.show_operator_hover(widget,op))
    def schedule_operator_hover_close(self):
        if getattr(self,'operator_hover_job',None):self.after_cancel(self.operator_hover_job)
        self.operator_hover_job=self.after(250,self.check_operator_hover)
    def check_operator_hover(self):
        self.operator_hover_job=None;x,y=self.winfo_pointerxy()
        def inside(w):return w and w.winfo_exists() and w.winfo_ismapped() and w.winfo_rootx()<=x<w.winfo_rootx()+w.winfo_width() and w.winfo_rooty()<=y<w.winfo_rooty()+w.winfo_height()
        if not inside(getattr(self,'operator_hover_anchor',None)) and not inside(getattr(self,'operator_popup',None)):self.close_operator_hover()
    def show_operator_hover(self,widget,op):
        self.operator_hover_job=None
        if not widget.winfo_exists() or not widget.winfo_ismapped():return
        pop=tk.Toplevel(self);self.operator_popup=pop;pop.withdraw();pop.overrideredirect(True);pop.transient(self)
        frame=tk.Frame(pop,bg='#ffffff',highlightbackground='#cbd4d8',highlightthickness=1,padx=5,pady=5);frame.pack(fill='both',expand=True);body=self.scroll(frame)
        card=OperatorCard(body,self,op,self.status(op)=='不可用',True);card.pack(fill='x');width=550;x=widget.winfo_rootx()+widget.winfo_width()+5;y=widget.winfo_rooty()
        if x+width>self.winfo_screenwidth():x=max(0,widget.winfo_rootx()-width-5)
        pop.geometry(f'{width}x300{x:+d}{y:+d}');pop.deiconify();pop.update_idletasks()
        def fit():
            if not pop.winfo_exists() or not widget.winfo_exists():return
            height=min(500,max(160,card.winfo_reqheight()+18));top=max(0,min(widget.winfo_rooty(),self.winfo_screenheight()-height));pop.geometry(f'{width}x{height}{x:+d}{top:+d}')
        pop.after(120,fit);pop.lift()
        def enter(event=None):
            if getattr(self,'operator_hover_job',None):self.after_cancel(self.operator_hover_job);self.operator_hover_job=None
        def bind_children(w):
            w.bind('<Enter>',enter,add='+');w.bind('<Leave>',lambda e:self.schedule_operator_hover_close(),add='+')
            for child in w.winfo_children():bind_children(child)
        bind_children(pop)
    def add_compact_cards(self,parent,ops):
        grid=ttk.Frame(parent);grid.pack(fill='x');ordered=sorted(ops,key=lambda o:(self.status(o)=='不可用',o['id']));cards=[CompactOperatorCard(grid,self,op) for op in ordered];state={'layout':None,'job':None}
        def reflow():
            state['job']=None
            if not grid.winfo_exists():return
            columns=max(1,grid.winfo_width()//315)
            if columns==state['layout']:return
            state['layout']=columns
            for i,card in enumerate(cards):card.grid(row=i//columns,column=i%columns,padx=(0,8),pady=(0,8),sticky='nw')
        def schedule(event=None):
            if state['job']:grid.after_cancel(state['job'])
            state['job']=grid.after(80,reflow)
        grid.bind('<Configure>',schedule);reflow()
        if not cards:ttk.Label(grid,text='暂无',foreground='#999999').grid(row=0,column=0,sticky='w')
        return cards
    def add_economy_section(self):
        section=CollapsibleSection(self.links,'经济');section.pack(fill='x',pady=(12,6));section.category='经济'
        def populate():
            for bond in ('奇迹','远见','投资人'):
                if not any(b['name']==bond for b in self.season.bonds):continue
                label=bond+('  · 已 Ban' if self.banned is not None and bond in self.banned else '')
                ttk.Label(section.content,text=label,font=('Noto Sans SC',10,'bold')).pack(anchor='w',pady=(8,5));self.add_compact_cards(section.content,[o for o in self.season.operators if bond in o['bonds']])
        section.on_expand=populate
    def close_graph_window(self):
        close=getattr(self,'graph_close',None)
        if close:close()
    def add_graph_panel(self,center,nodes,edges):
        toolbar=ttk.Frame(self.links);toolbar.pack(fill='x',pady=(8,2));ttk.Label(toolbar,text='盟约关系图',font=('Noto Sans SC',11,'bold')).pack(side='left')
        graph=RelationshipGraph(self.links,self,center,nodes,edges);graph.pack(fill='x',pady=6)
        def open_window():
            if getattr(self,'graph_window',None) and self.graph_window.winfo_exists():self.graph_window.lift();return
            window=tk.Toplevel(self);self.graph_window=window;window.title(center+' · 盟约关系图');window.attributes('-topmost',True);window.overrideredirect(True);window.resizable(False,False)
            floating=RelationshipGraph(window,self,graph.center,graph.nodes,graph.edges);floating.base_width=900;floating.zoom=.65;floating.focus=graph.focus;floating.pack();graph.pack_forget()
            def zoom(delta):
                floating.zoom=round(max(.45,min(1.25,floating.zoom+delta)),2);w=round(900*floating.zoom);h=round(850*floating.zoom);x=window.winfo_x();y=window.winfo_y();floating.configure(width=w,height=h);window.geometry(f'{w}x{h}{x:+d}{y:+d}');floating.schedule_draw()
            def close():
                self.graph_close=None;self.graph_window=None
                if graph.winfo_exists() and toolbar.winfo_exists():graph.focus=floating.focus;graph.pack(fill='x',pady=6,after=toolbar);graph.schedule_draw()
                if window.winfo_exists():window.destroy()
            self.graph_close=close;window.protocol('WM_DELETE_WINDOW',close)
            state={'minimizing':False,'hide_job':None,'drag':None}
            def minimize():state['minimizing']=True;window.overrideredirect(False);window.iconify()
            def restore(event):
                if event.widget is window and state['minimizing'] and window.state()=='normal':state['minimizing']=False;window.after_idle(lambda:window.overrideredirect(True))
            window.bind('<Map>',restore,add='+')
            controls=[]
            for name in ('minimize','close'):
                control=tk.Canvas(floating,width=30,height=30,bg='#f5f7f8',highlightthickness=0,bd=0,cursor='hand2');control.create_oval(2,2,28,28,fill='#e7ecee',outline='#c6d0d2')
                if name=='minimize':control.create_line(9,17,21,17,fill='#526469',width=2)
                else:control.create_line(10,10,20,20,fill='#526469',width=2);control.create_line(20,10,10,20,fill='#526469',width=2)
                control.bind('<Button-1>',lambda event,fn=minimize if name=='minimize' else close:fn());controls.append(control)
            def show_controls(event=None):
                if state['hide_job']:window.after_cancel(state['hide_job']);state['hide_job']=None
                for control,x in zip(controls,(-44,-9)):control.place(relx=1,x=x,y=8,anchor='ne');tk.Misc.tkraise(control)
            def hide_if_outside():
                state['hide_job']=None
                if not window.winfo_exists():return
                x,y=window.winfo_pointerxy();inside=window.winfo_rootx()<=x<window.winfo_rootx()+window.winfo_width() and window.winfo_rooty()<=y<window.winfo_rooty()+window.winfo_height()
                if not inside:
                    for control in controls:control.place_forget()
            def schedule_hide(event=None):
                if state['hide_job']:window.after_cancel(state['hide_job'])
                state['hide_job']=window.after(150,hide_if_outside)
            for widget in [floating]+controls:widget.bind('<Enter>',show_controls,add='+');widget.bind('<Leave>',schedule_hide,add='+')
            def wheel(event):
                if event.delta:zoom(.1 if event.delta>0 else -.1)
                return 'break'
            floating.bind('<MouseWheel>',wheel,add='+')
            for control in controls:control.bind('<MouseWheel>',wheel,add='+')
            def drag_start(event):state['drag']=(event.x_root,event.y_root,window.winfo_x(),window.winfo_y())
            def drag_move(event):
                if state['drag']:
                    sx,sy,left,top=state['drag'];window.geometry(f'{left+event.x_root-sx:+d}{top+event.y_root-sy:+d}')
            floating.bind('<ButtonPress-1>',drag_start,add='+');floating.bind('<B1-Motion>',drag_move,add='+')
            zoom(0)
        ttk.Button(toolbar,text='悬浮窗口',command=open_window).pack(side='right')
        return graph
    def show_small_links(self):
        self.close_graph_window();self.close_operator_hover()
        for w in self.links.winfo_children():w.destroy()
        name=self.selected_small.get();connections=self.small_intersections(name)
        if connections:
            edges=[{'a':name,'b':other,'kind':'secondary','ops':ops} for other,ops in connections.items()];self.add_graph_panel(name,list(connections),edges)
        else:ttk.Label(self.links,text='没有同时拥有其他战斗小盟约的干员。',foreground='#888888').pack(anchor='w',pady=20)
        section=CollapsibleSection(self.links,name+' · 全部干员');section.pack(fill='x',pady=5);section.category='全部干员';items=[o for o in self.season.operators if name in o['bonds']];section.on_expand=lambda s=section,items=items:self.add_compact_cards(s.content,items)
        for other,ops in sorted(connections.items(),key=lambda pair:self.banned is not None and pair[0] in self.banned):
            section=CollapsibleSection(self.links,other+('  · 已 Ban' if self.banned is not None and other in self.banned else ''));section.pack(fill='x',pady=5);section.on_expand=lambda s=section,items=ops:self.add_compact_cards(s.content,items)
        self.add_economy_section()
    def show_links(self):
        self.close_graph_window();self.close_operator_hover()
        for w in self.links.winfo_children():w.destroy()
        core=self.core.get(); ops=[o for o in self.season.operators if core in o['bonds']]; small=[b['name'] for b in self.season.bonds if b['category']=='附加盟约' and b['name'] in self.combat_small_names];associated=[x for x in small if any(x in o['bonds'] for o in ops)]
        if associated:
            edges=[{'a':core,'b':bond,'kind':'core','ops':[o for o in ops if bond in o['bonds']]} for bond in associated]
            for i,a in enumerate(associated):
                for b in associated[i+1:]:
                    connectors=[o for o in self.season.operators if core not in o['bonds'] and a in o['bonds'] and b in o['bonds']]
                    if connectors:edges.append({'a':a,'b':b,'kind':'secondary','ops':connectors})
            self.add_graph_panel(core,associated,edges)
        section=CollapsibleSection(self.links,core+' · 全部干员');section.pack(fill='x',pady=5);section.category='全部干员';section.on_expand=lambda s=section,items=ops:self.add_compact_cards(s.content,items)
        for bond in sorted(associated,key=lambda value:self.banned is not None and value in self.banned):
            owned=[o for o in ops if bond in o['bonds']]; others=[o for o in self.season.operators if bond in o['bonds'] and core not in o['bonds']];others.sort(key=lambda o:(self.status(o)=='不可用',o['trait_type']!='持续叠加'))
            section=CollapsibleSection(self.links,bond+('  · 已 Ban' if self.banned is not None and bond in self.banned else ''));section.pack(fill='x',pady=6);box=section.content
            def populate(box=box,owned=owned,others=others):
                for title,items in [('大盟约干员',owned),('可补充的其他干员',others)]:
                    ttk.Label(box,text=title,foreground='#777777').pack(anchor='w',pady=(4,5));self.add_compact_cards(box,items)
            section.on_expand=populate
        self.add_economy_section()
    def edit_bans(self):
        win=tk.Toplevel(self);win.title('本局信息');win.geometry('650x650'); body=self.scroll(win);vs={}
        for category in ('核心盟约','附加盟约'):
            box=ttk.LabelFrame(body,text=category+'（勾选被 Ban）',padding=8);box.pack(fill='x',pady=5)
            for i,b in enumerate(x for x in self.season.bonds if x['category']==category):
                var=tk.BooleanVar(value=self.banned is not None and b['name'] in self.banned);vs[b['name']]=var;ttk.Checkbutton(box,text=b['name'],variable=var).grid(row=i//4,column=i%4,sticky='w',padx=8,pady=3)
        ttk.Label(body,text='特训敌人种类（用顿号分隔）').pack(anchor='w'); enemy=tk.StringVar(value=self.enemies);ttk.Entry(body,textvariable=enemy).pack(fill='x')
        def save():self.banned={n for n,v in vs.items() if v.get()};self.enemies=enemy.get().strip();win.destroy();self.redraw()
        ttk.Button(body,text='确认并应用',command=save).pack(pady=12)
    def reset(self):self.banned=None;self.enemies='';self.redraw()
    def screenshot(self):
        path=filedialog.askopenfilename(filetypes=[('图片','*.png *.jpg *.jpeg *.bmp')])
        if not path:return
        self.recognize_screenshot(path)
    def paste_screenshot(self,event):
        try:
            content=ImageGrab.grabclipboard()
        except Exception as error:
            messagebox.showerror('无法读取剪贴板',str(error));return 'break'
        is_image=isinstance(content,Image.Image) or (isinstance(content,list) and len(content)==1 and Path(content[0]).suffix.lower() in ('.png','.jpg','.jpeg','.bmp'))
        if is_image:
            self.clipboard_screenshot(content);return 'break'
        if isinstance(event.widget,(tk.Entry,ttk.Entry,tk.Text,ttk.Combobox)):
            return None
        messagebox.showinfo('没有截图','剪贴板中没有可用的图片。请先复制截图，再按 Ctrl+V。')
        return 'break'
    def clipboard_screenshot(self,content=None):
        try:
            image=ImageGrab.grabclipboard() if content is None else content
            if isinstance(image,Image.Image):
                with tempfile.NamedTemporaryFile(prefix='garrison-',suffix='.png',delete=False) as temp:
                    path=Path(temp.name)
                try:
                    image.save(path,format='PNG')
                except Exception:
                    path.unlink(missing_ok=True)
                    raise
                self.recognize_screenshot(path,temporary=True)
            elif isinstance(image,list) and len(image)==1 and Path(image[0]).suffix.lower() in ('.png','.jpg','.jpeg','.bmp'):
                self.recognize_screenshot(image[0])
            else:
                messagebox.showinfo('没有截图','剪贴板中没有可用的图片。请先使用截图工具复制截图，再重试。')
        except Exception as error:
            messagebox.showerror('无法读取剪贴板',str(error))
    def recognize_screenshot(self,path,temporary=False):
        progress=tk.Toplevel(self);progress.title('正在识别');progress.geometry('300x90');ttk.Label(progress,text='正在识别本局信息，请稍候…',padding=20).pack();progress.transient(self)
        def task():
            try:
                from recognize import recognize
                result=recognize(path,self.season.path)
                expected={b['name'] for b in self.season.bonds}
                if result['banned'] | result['available'] != expected:raise ValueError('识别结果与当前赛季盟约不一致')
                self.after(0,lambda:finish(result,None))
            except Exception as error:
                detail=str(error);self.after(0,lambda:finish(None,detail))
            finally:
                if temporary:Path(path).unlink(missing_ok=True)
        def finish(result,error):
            progress.destroy()
            if error:messagebox.showwarning('识别失败',error+'\n请重新上传包含全部盟约图标的截图，当前本局信息未改变。');return
            msg='被 Ban 的盟约：\n'+'、'.join(sorted(result['banned']))+'\n\n确认将结果应用到本局？'
            if messagebox.askyesno('确认识别结果',msg):self.banned=result['banned'];self.redraw()
        threading.Thread(target=task,daemon=True).start()
    def render_operators(self):
        if getattr(self,'filter_close_job',None):self.after_cancel(self.filter_close_job);self.filter_close_job=None
        if getattr(self,'search_job',None):self.after_cancel(self.search_job);self.search_job=None
        if getattr(self,'filterpopup',None) and self.filterpopup.winfo_exists():self.filterpopup.destroy()
        p=self.pages['干员'];self.clear(p);self.filterbar=ttk.Frame(p);self.filterbar.pack(fill='x');self.search=tk.StringVar();self.search_job=None;self.applied_search='';ttk.Label(self.filterbar,text='干员图鉴',style='Title.TLabel').pack(side='left');e=ttk.Entry(self.filterbar,textvariable=self.search,width=23);e.pack(side='right',padx=6);self.search.trace_add('write',self.schedule_search)
        controls=ttk.Frame(p);controls.pack(fill='x',pady=(12,3));self.filterbutton=ttk.Button(controls,text='筛选条件  ▾',command=self.open_filter_panel);self.filterbutton.pack(side='left')
        self.filterpopup=tk.Toplevel(self);self.filterpopup.withdraw();self.filterpopup.overrideredirect(True);self.filterpopup.transient(self)
        self.filterdetail=tk.Frame(self.filterpopup,bg='#ffffff',padx=14,pady=12,highlightbackground='#d7dedd',highlightthickness=1);self.filterdetail.pack(fill='both',expand=True);self.filter_open=False;self.filter_close_job=None
        popup_header=ttk.Frame(self.filterdetail);popup_header.pack(fill='x',pady=(0,5));ttk.Label(popup_header,text='筛选条件',font=('Noto Sans SC',11,'bold')).pack(side='left');ttk.Button(popup_header,text='清除全部',command=self.clear_filter).pack(side='right')
        groups={'阶数':['Ⅰ','Ⅱ','Ⅲ','Ⅳ','Ⅴ','Ⅵ'],'核心盟约':[x['name'] for x in self.season.bonds if x['category']=='核心盟约'],'附加盟约':[x['name'] for x in self.season.bonds if x['category']=='附加盟约'],'特质':sorted(set(o['trait_type'] for o in self.season.operators))};self.filterchips={}
        for group,values in groups.items():
            line=ttk.Frame(self.filterdetail);line.pack(fill='x',pady=2);ttk.Label(line,text=group,width=9,foreground='#777777').grid(row=0,column=0,sticky='nw',pady=9)
            for i,value in enumerate(values):
                b=next((b for b in self.season.bonds if b['name']==value),None);icon=self.season.bond_icon(b['icon_url'],28,disabled=self.banned is not None and value in self.banned) if b else None
                chip=Chip(line,value,lambda g=group,v=value:self.toggle_filter(g,v),selected=value in self.filters.get(group,set()),icon=icon,width=116);chip.grid(row=i//6,column=1+i%6,padx=(0,10),pady=5,sticky='w');self.filterchips[group,value]=chip
                if b:self.bind_bond_hover(chip,value)
        def bind_hover(widget):
            widget.bind('<Enter>',self.open_filter_panel,add='+');widget.bind('<Leave>',self.schedule_filter_close,add='+')
            for child in widget.winfo_children():bind_hover(child)
        bind_hover(self.filterbutton);bind_hover(self.filterdetail)
        self.filtertext=ttk.Label(p,text='',foreground='#8a8a8a');self.filtertext.pack(anchor='w',pady=4);self.opbody=self.scroll(p);self.operator_list()
    def open_filter_panel(self,event=None):
        if self.filter_close_job:
            self.after_cancel(self.filter_close_job);self.filter_close_job=None
        if not self.filter_open:
            self.filterpopup.update_idletasks();width=self.filterdetail.winfo_reqwidth();height=self.filterdetail.winfo_reqheight();x=self.filterbutton.winfo_rootx();y=self.filterbutton.winfo_rooty()+self.filterbutton.winfo_height()
            x=max(0,min(x,self.winfo_screenwidth()-width));y=y if y+height<=self.winfo_screenheight() else max(0,self.filterbutton.winfo_rooty()-height)
            self.filterpopup.geometry(f'{width}x{height}{x:+d}{y:+d}');self.filterpopup.deiconify();self.filterpopup.lift();self.filter_open=True
    def schedule_filter_close(self,event=None):
        if self.filter_close_job:self.after_cancel(self.filter_close_job)
        self.filter_close_job=self.after(180,self.close_filter_if_outside)
    def close_filter_if_outside(self):
        self.filter_close_job=None
        if not self.filterpopup.winfo_exists():return
        x,y=self.winfo_pointerxy()
        def inside(widget):
            left=widget.winfo_rootx();top=widget.winfo_rooty();return left<=x<left+widget.winfo_width() and top<=y<top+widget.winfo_height()
        bond_pop=getattr(self,'bond_popup',None)
        if not inside(self.filterbutton) and not inside(self.filterpopup) and not (bond_pop and bond_pop.winfo_exists() and inside(bond_pop)):
            self.filterpopup.withdraw();self.filter_open=False
    def toggle_filter(self,group,value):
        selected=self.filters.setdefault(group,set())
        if value in selected:selected.remove(value)
        else:selected.add(value)
        self.filterchips[group,value].selected=value in selected;self.filterchips[group,value].paint();self.operator_list()
    def schedule_search(self,*args):
        if self.search_job:self.after_cancel(self.search_job)
        self.search_job=self.after(350,self.apply_search)
    def apply_search(self):
        self.search_job=None
        if self.search.get()!=self.applied_search:self.operator_list()
    def clear_filter(self):
        self.filters={}
        for chip in self.filterchips.values():chip.selected=False;chip.paint()
        self.operator_list()
    def filter_dialog(self):
        win=tk.Toplevel(self);win.title('筛选标签');win.geometry('720x650');body=self.scroll(win); groups={'阶数':['Ⅰ','Ⅱ','Ⅲ','Ⅳ','Ⅴ','Ⅵ'],'核心盟约':[x['name'] for x in self.season.bonds if x['category']=='核心盟约'],'附加盟约':[x['name'] for x in self.season.bonds if x['category']=='附加盟约'],'特质':sorted(set(o['trait_type'] for o in self.season.operators))};vs={}
        for group,values in groups.items():
            box=ttk.LabelFrame(body,text=group,padding=5);box.pack(fill='x',pady=4)
            for i,value in enumerate(values):
                v=tk.BooleanVar(value=value in self.filters.get(group,set()));vs[group,value]=v;ttk.Checkbutton(box,text=value,variable=v).grid(row=i//5,column=i%5,sticky='w',padx=7)
        def apply():
            self.filters={g:{v for (k,v),var in vs.items() if k==g and var.get()} for g in groups};win.destroy();self.operator_list()
        ttk.Button(body,text='应用筛选',command=apply).pack(pady=10)
    def operator_list(self):
        if getattr(self,'search_job',None):self.after_cancel(self.search_job);self.search_job=None
        self.applied_search=self.search.get()
        if getattr(self,'card_reflow_job',None):self.after_cancel(self.card_reflow_job);self.card_reflow_job=None
        if getattr(self,'card_load_job',None):self.after_cancel(self.card_load_job);self.card_load_job=None
        for w in self.opbody.winfo_children():w.destroy()
        self.filtertext.config(text='　'.join(k+'：'+'、'.join(sorted(v)) for k,v in self.filters.items() if v) or '未选择标签')
        matches=[]
        for op in self.season.operators:
            if self.search.get().lower() not in ' '.join(n['name'] for n in op['names']).lower():continue
            fields={'阶数':{op['tier']},'核心盟约':set(op['bonds']),'附加盟约':set(op['bonds']),'特质':{op['trait_type']}}; active=[(v,fields[k]) for k,v in self.filters.items() if v]
            if any(not(v & f) for v,f in active):continue
            full=all(v<=f for v,f in active);matches.append((self.status(op)=='不可用',not full,op))
        matches.sort(key=lambda x:(x[0],x[1],x[2]['id']))
        ttk.Label(self.opbody,text=f'共 {len(matches)} 条').pack(anchor='w')
        self.cardgrid=ttk.Frame(self.opbody);self.cardgrid.pack(fill='x',pady=(4,0));self.cards=[];self.card_matches=matches;self.card_loaded=0;self.card_layout=None
        self.load_more_button=ttk.Button(self.opbody,text='加载更多干员',command=self.load_operator_cards)
        def add_card(unavailable,partial,op):
            return OperatorCard(self.cardgrid,self,op,unavailable,partial)
        self.make_operator_card=add_card
        self.cardgrid.bind('<Configure>',self.schedule_card_reflow)
        def on_scroll(first,last):
            self.opbody.scrollbar.set(first,last)
            if self.tabs.select()==str(self.pages['干员']) and self.opbody.scroll_canvas.winfo_height()>100 and float(last)>.94 and self.card_loaded<len(self.card_matches) and not getattr(self,'card_load_job',None):
                self.card_load_job=self.after(300,self.load_operator_cards)
        self.opbody.scroll_canvas.configure(yscrollcommand=on_scroll);self.opbody.scroll_canvas.yview_moveto(0);self.load_operator_cards()
    def schedule_card_reflow(self,event=None):
        if getattr(self,'card_reflow_job',None):self.after_cancel(self.card_reflow_job)
        self.card_reflow_job=self.after(150,self.reflow_operator_cards)
    def reflow_operator_cards(self):
        self.card_reflow_job=None
        if not self.cardgrid.winfo_exists():return
        available=max(360,self.cardgrid.winfo_width());columns=max(1,(available+12)//500);width=min(560,max(360,(available-12*(columns-1))//columns));layout=(columns,width,len(self.cards))
        if layout==self.card_layout:return
        self.card_layout=layout
        for i,card in enumerate(self.cards):
            card.configure(width=width);card.grid(row=i//columns,column=i%columns,sticky='nw',padx=(0,12),pady=(0,12))
    def load_operator_cards(self):
        self.card_load_job=None
        if not self.cardgrid.winfo_exists():return
        end=min(self.card_loaded+24,len(self.card_matches))
        for unavailable,partial,op in self.card_matches[self.card_loaded:end]:self.cards.append(self.make_operator_card(unavailable,partial,op))
        self.card_loaded=end;self.card_layout=None;self.reflow_operator_cards()
        if end<len(self.card_matches):self.load_more_button.pack(anchor='center',pady=10)
        else:self.load_more_button.pack_forget()
    def render_bonds(self):
        self.render_catalog('盟约')
    def catalog_details(self,parent,kind,item):
        if kind=='盟约':
            count,parts=alliance_effect_sections(item['effect'])
            if count:ttk.Label(parent,text='激活所需人数  '+count,foreground='#148c72',font=('Noto Sans SC',10,'bold')).pack(anchor='w',pady=(3,6))
            for text in parts:
                box=RichEffect(parent,text);box.pack(fill='x',pady=(0,6))
        else:
            if kind=='装备':
                ttk.Label(parent,text=item['tier']+'  ·  售价 '+item['price'],foreground='#71807e').pack(anchor='w',pady=(2,6))
            details=format_strategy_details(item['details']) if kind=='策略' else item['details']
            RichEffect(parent,details).pack(fill='x',pady=(0,6))
    def bind_bond_hover(self,widget,name):
        widget.bind('<Enter>',lambda event:self.start_bond_hover(widget,name),add='+');widget.bind('<Leave>',lambda event:self.schedule_bond_hover_close(),add='+')
    def close_bond_hover(self):
        if getattr(self,'bond_hover_job',None):self.after_cancel(self.bond_hover_job);self.bond_hover_job=None
        popup=getattr(self,'bond_popup',None)
        if popup and popup.winfo_exists():popup.destroy()
        self.bond_popup=None;self.bond_anchor=None
    def start_bond_hover(self,widget,name,rect=None):
        self.close_bond_hover();self.bond_anchor=(widget,rect)
        self.bond_hover_job=self.after(350,lambda:self.show_bond_hover(widget,name,rect))
    def schedule_bond_hover_close(self):
        if getattr(self,'bond_hover_job',None):self.after_cancel(self.bond_hover_job)
        self.bond_hover_job=self.after(250,self.check_bond_hover_pointer)
    def check_bond_hover_pointer(self):
        self.bond_hover_job=None;x,y=self.winfo_pointerxy();anchor=getattr(self,'bond_anchor',None);popup=getattr(self,'bond_popup',None)
        def inside(widget,rect=None):
            if not widget or not widget.winfo_exists() or not widget.winfo_ismapped():return False
            left,top=widget.winfo_rootx(),widget.winfo_rooty();width,height=widget.winfo_width(),widget.winfo_height()
            if rect:dx,dy,width,height=rect;left+=dx;top+=dy
            return left<=x<left+width and top<=y<top+height
        if not (anchor and inside(anchor[0],anchor[1])) and not inside(popup):
            self.close_bond_hover()
            if getattr(self,'filter_open',False):self.schedule_filter_close()
            if getattr(self,'home_past_top',False):self.schedule_home_hover_close()
    def show_bond_hover(self,widget,name,rect=None):
        self.bond_hover_job=None
        if not widget.winfo_exists() or not widget.winfo_ismapped():return
        item=next((b for b in self.season.bonds if b['name']==name),None)
        if not item:return
        pop=tk.Toplevel(self);self.bond_popup=pop;pop.withdraw();pop.overrideredirect(True);pop.transient(self)
        shell=tk.Frame(pop,bg='#ffffff',highlightbackground='#cbd4d8',highlightthickness=1,padx=12,pady=10);shell.pack(fill='both',expand=True)
        title=ttk.Label(shell,text=name+'  ·  '+item['category'],font=('Noto Sans SC',12,'bold'));title.pack(anchor='w',pady=(0,4));content=self.scroll(shell);self.catalog_details(content,'盟约',item)
        width=500;x=widget.winfo_rootx()+(rect[0] if rect else 0);y=widget.winfo_rooty()+(rect[1]+rect[3] if rect else widget.winfo_height());x=max(0,min(x,self.winfo_screenwidth()-width));pop.geometry(f'{width}x200{x:+d}{y:+d}');pop.deiconify();pop.lift()
        fit={'job':None}
        def fit_content():
            fit['job']=None
            if not pop.winfo_exists() or not widget.winfo_exists():return
            height=min(500,max(90,content.winfo_reqheight()+title.winfo_reqheight()+30));top=y if y+height<=self.winfo_screenheight() else max(0,widget.winfo_rooty()-height)
            if pop.winfo_height()!=height or pop.winfo_y()!=top:pop.geometry(f'{width}x{height}{x:+d}{top:+d}')
        def schedule_fit(event=None):
            if fit['job']:pop.after_cancel(fit['job'])
            fit['job']=pop.after(100,fit_content)
        content.bind('<Configure>',schedule_fit,add='+');schedule_fit()
        def enter(event=None):
            if getattr(self,'bond_hover_job',None):self.after_cancel(self.bond_hover_job);self.bond_hover_job=None
        def bind_children(w):
            w.bind('<Enter>',enter,add='+');w.bind('<Leave>',lambda event:self.schedule_bond_hover_close(),add='+')
            for child in w.winfo_children():bind_children(child)
        bind_children(pop)
    def close_catalog_hover(self):
        job=getattr(self,'catalog_hover_job',None)
        if job:self.after_cancel(job);self.catalog_hover_job=None
        popup=getattr(self,'catalog_popup',None)
        if popup and popup.winfo_exists():popup.destroy()
        self.catalog_popup=None;self.catalog_hover_card=None
    def render_catalog(self,kind):
        self.close_catalog_hover();p=self.pages[kind];self.clear(p);header=ttk.Frame(p);header.pack(fill='x',pady=(0,8));ttk.Label(header,text=kind+'图鉴',style='Title.TLabel').pack(side='left');query=tk.StringVar();ttk.Entry(header,textvariable=query,width=22).pack(side='right');body=self.scroll(p);grid=ttk.Frame(body);grid.pack(fill='x');cards=[];state={'columns':None,'search_job':None}
        items=self.season.bonds if kind=='盟约' else [dict(r) for r in self.season.db.execute('select * from '+('strategies' if kind=='策略' else 'equipment'))]
        def reflow(event=None):
            width=max(300,grid.winfo_width());columns=max(1,width//(500 if kind=='装备' else 300))
            if state['columns']==columns:return
            for col in range(8):grid.columnconfigure(col,weight=1 if col<columns else 0,uniform='catalog' if col<columns else '')
            for i,card in enumerate(cards):card.grid(row=i//columns,column=i%columns,sticky='nsew',padx=(0,10),pady=(0,10))
            state['columns']=columns
        def show_popup(card,item):
            if not card.winfo_exists() or card.expanded:return
            self.close_catalog_hover();self.catalog_hover_card=card;pop=tk.Toplevel(self);self.catalog_popup=pop;pop.withdraw();pop.overrideredirect(True);pop.transient(self)
            shell=tk.Frame(pop,bg='#ffffff',highlightbackground='#cbd4d8',highlightthickness=1,padx=12,pady=10);shell.pack(fill='both',expand=True)
            title=item['character']+'  ·  '+item['name'] if kind=='策略' else item['name']
            popup_title=ttk.Label(shell,text=title,font=('Noto Sans SC',12,'bold'));popup_title.pack(anchor='w',pady=(0,4));content=self.scroll(shell);self.catalog_details(content,kind,item)
            width=500;pop.geometry(f'{width}x180-32000-32000');pop.deiconify();pop.update_idletasks();pop.update_idletasks()
            height=min(500,max(100,content.winfo_reqheight()+58));x=card.winfo_rootx()+card.winfo_width()+5;y=card.winfo_rooty()
            if x+width>self.winfo_screenwidth():x=max(0,card.winfo_rootx()-width-5)
            y=max(0,min(y,self.winfo_screenheight()-height));pop.geometry(f'{width}x{height}{x:+d}{y:+d}');pop.deiconify();pop.lift()
            fit_state={'job':None}
            def fit_content():
                fit_state['job']=None
                if not pop.winfo_exists() or not card.winfo_exists():return
                desired=min(500,max(90,content.winfo_reqheight()+popup_title.winfo_reqheight()+30));new_y=max(0,min(card.winfo_rooty(),self.winfo_screenheight()-desired))
                if pop.winfo_height()!=desired:pop.geometry(f'{width}x{desired}{x:+d}{new_y:+d}')
            def schedule_fit(event=None):
                if fit_state['job']:pop.after_cancel(fit_state['job'])
                fit_state['job']=pop.after(100,fit_content)
            content.bind('<Configure>',schedule_fit,add='+');schedule_fit()
            def leave(event=None):self.catalog_hover_job=self.after(250,check_pointer)
            def enter(event=None):
                if getattr(self,'catalog_hover_job',None):self.after_cancel(self.catalog_hover_job);self.catalog_hover_job=None
            def bind_all_children(w):
                w.bind('<Enter>',enter,add='+');w.bind('<Leave>',leave,add='+')
                for child in w.winfo_children():bind_all_children(child)
            bind_all_children(pop)
        def check_pointer():
            self.catalog_hover_job=None;card=getattr(self,'catalog_hover_card',None);pop=getattr(self,'catalog_popup',None);x,y=self.winfo_pointerxy()
            def inside(w):return w and w.winfo_exists() and w.winfo_rootx()<=x<w.winfo_rootx()+w.winfo_width() and w.winfo_rooty()<=y<w.winfo_rooty()+w.winfo_height()
            if not inside(card) and not inside(pop):self.close_catalog_hover()
        def populate():
            state['search_job']=None
            if not grid.winfo_exists():return
            self.close_catalog_hover()
            for c in cards:c.destroy()
            cards.clear();needle=query.get().strip().casefold()
            for item in items:
                text=item['effect'] if kind=='盟约' else item['details']+(' '+item['character'] if kind=='策略' else '')
                if needle and needle not in (item['name']+' '+text).casefold():continue
                card=tk.Frame(grid,bg='#f4f6f7',highlightbackground='#cbd4d8',highlightthickness=1,padx=10,pady=9);card.expanded=False;card.details=None;cards.append(card)
                cursor='arrow' if kind=='装备' else 'hand2';top=tk.Frame(card,bg='#f4f6f7',cursor=cursor);top.pack(fill='x');icon=self.season.bond_icon(item['icon_url'],42,disabled=self.banned is not None and item['name'] in self.banned) if kind=='盟约' else self.season.image(item['image_url'],(42,42))
                if icon:lab=tk.Label(top,image=icon,bg='#f4f6f7',cursor=cursor);lab.image=icon;lab.pack(side='left',padx=(0,10))
                title=item['character']+'  ·  '+item['name'] if kind=='策略' else item['name']
                tk.Label(top,text=title,font=('Noto Sans SC',11,'bold'),bg='#f4f6f7',fg='#242b2d',anchor='w',cursor=cursor).pack(side='left',fill='x',expand=True)
                indicator=tk.Label(top,text='＋',font=('Noto Sans SC',12),bg='#f4f6f7',fg='#899190',cursor=cursor)
                if kind!='装备':indicator.pack(side='right')
                def toggle(event=None,c=card,it=item,mark=indicator):
                    self.close_catalog_hover()
                    if c.expanded:c.details.destroy();c.details=None;c.expanded=False;mark.config(text='＋')
                    else:
                        c.details=ttk.Frame(c,padding=(4,10,4,0));c.details.pack(fill='x');self.catalog_details(c.details,kind,it);c.expanded=True;mark.config(text='−')
                def enter(event=None,c=card,it=item):
                    if getattr(self,'catalog_hover_job',None):self.after_cancel(self.catalog_hover_job)
                    if not c.expanded:self.catalog_hover_job=self.after(350,lambda:show_popup(c,it))
                def leave(event=None):
                    if getattr(self,'catalog_hover_job',None):self.after_cancel(self.catalog_hover_job)
                    self.catalog_hover_job=self.after(250,check_pointer)
                if kind=='装备':
                    card.details=ttk.Frame(card,padding=(4,10,4,0));card.details.pack(fill='x');self.catalog_details(card.details,kind,item);card.expanded=True
                else:
                    for w in [top]+top.winfo_children():w.bind('<Button-1>',toggle);w.bind('<Enter>',enter);w.bind('<Leave>',leave)
            state['columns']=None;reflow()
        def schedule(*args):
            if state['search_job']:self.after_cancel(state['search_job'])
            state['search_job']=self.after(350,populate)
        query.trace_add('write',schedule);grid.bind('<Configure>',reflow);populate()
    def render_entries(self,kind):
        if kind in ('策略','装备'):self.render_catalog(kind);return
        p=self.pages[kind];self.clear(p);query=tk.StringVar();entry=ttk.Entry(p,textvariable=query);entry.pack(fill='x',pady=5);body=self.scroll(p);table='strategies' if kind=='策略' else 'equipment'
        def show(*_):
            for w in body.winfo_children():w.destroy()
            for row in self.season.db.execute('select * from '+table+' where name like ? or details like ?',('%'+query.get()+'%','%'+query.get()+'%')):
                box=tk.Frame(body,bg='#f8f9f9',padx=16,pady=14,highlightbackground='#eeeeee',highlightthickness=1);box.pack(fill='x',pady=5);icon=self.season.image(row['image_url'],(48,48))
                if icon: label=tk.Label(box,image=icon,bg='#f8f9f9');label.image=icon;label.pack(side='left',anchor='n',padx=(0,14))
                details=tk.Frame(box,bg='#f8f9f9');details.pack(side='left',fill='x',expand=True);extra=(row['character']+'　'+row['role']) if kind=='策略' else (row['tier']+'　售价 '+row['price']);tk.Label(details,text=row['name']+'   '+extra,bg='#f8f9f9',fg='#202123',font=('Noto Sans SC',10,'bold'),anchor='w').pack(fill='x');tk.Label(details,text=row['details'],bg='#f8f9f9',fg='#555b5a',wraplength=850,justify='left',anchor='w').pack(fill='x',pady=(5,0))
        query.trace_add('write',show);show()

if __name__=='__main__':App().mainloop()
