from PIL import Image, ImageDraw
import sys
M=['sd15-inpainting','dreamshaper-8-inpainting','realvisxl-v5']
P=['landscape','interior','portrait','product2']
OUT=r'C:\AI\overnight-scratch\fix-worktree\docs\evidence\daytime-2026-10-09\expand-models'
H=330
for pct in (25,60):
    rows=[]
    for p in P:
        ims=[]
        for m in M:
            try: im=Image.open(f'gimp/expand/{m}/{p}-e{pct}/after-full.png').convert('RGB')
            except Exception: im=Image.new('RGB',(300,H),'grey')
            im=im.resize((int(im.width*H/im.height),H)); d=ImageDraw.Draw(im); d.rectangle((0,0,im.width,13),fill='black'); d.text((2,1),f'{p} {pct}% {m}',fill='white'); ims.append(im)
        r=Image.new('RGB',(sum(i.width for i in ims),H));x=0
        for i in ims:r.paste(i,(x,0));x+=i.width
        rows.append(r)
    W=max(r.width for r in rows);S=Image.new('RGB',(W,H*len(rows)))
    for k,r in enumerate(rows):S.paste(r,(0,k*H))
    S.save(f'{OUT}\sheet-{pct}.jpg',quality=78)
