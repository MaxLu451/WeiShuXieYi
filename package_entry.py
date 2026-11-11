"""Entry point for the Windows distribution, including a noninteractive check."""
import json, sys, traceback
from pathlib import Path
import app

if __name__=='__main__':
    if len(sys.argv)>2 and sys.argv[1]=='--self-check':
        output=Path(sys.argv[2]);result={}
        try:
            import cv2, numpy, recognize
            window=app.App();window.update()
            result.update(operators=len(window.season.operators),bonds=len(window.season.bonds),strategies=window.season.db.execute('select count(*) from strategies').fetchone()[0],equipment=window.season.db.execute('select count(*) from equipment').fetchone()[0],opencv=cv2.__version__,numpy=numpy.__version__)
            assert result['operators']>0 and result['bonds']>0 and result['strategies']>0 and result['equipment']>0
            assert window.season.bond_icon(window.season.bonds[0]['icon_url'],28)
            core=next(b['name'] for b in window.season.bonds if b['category']=='核心盟约');window.corechips[core].activate();window.update()
            diagram=next(w for w in window.links.winfo_children() if isinstance(w,app.RelationshipGraph));diagram.draw_graph();assert diagram.photo.width()>0;result['diagram_edges']=len(diagram.edges)
            if len(sys.argv)>3:
                detected=recognize.recognize(sys.argv[3],window.season.path);result['banned_count']=len(detected['banned'])
            window.destroy();result['ok']=True
        except Exception:
            result={'ok':False,'error':traceback.format_exc()}
        output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        sys.exit(0 if result['ok'] else 1)
    app.App().mainloop()
