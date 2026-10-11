from PIL import Image, ImageDraw
cs=['fabric-damaged-large','texture-damaged-huge','product-remove-large-cup','architecture-remove-small-ac']
W=480;rows=[]
for c in cs:
    a=Image.open(f'../benchmark/runs/flux1-fill-dev-gguf-q4/{c}/after-full.png').convert('RGB')
    b=Image.open(f'gimp/fluxhard/flux1-fill-dev-gguf-q4/{c}/after-full.png').convert('RGB')
    ims=[]
    for im,l in((a,'old'),(b,'new: hard mask, no DiffDiff')):
        im=im.resize((W,int(im.height*W/im.width)));d=ImageDraw.Draw(im);d.rectangle((0,0,W,14),fill='black');d.text((2,1),c+' '+l,fill='white');ims.append(im)
    h=max(i.height for i in ims);r=Image.new('RGB',(2*W,h));r.paste(ims[0],(0,0));r.paste(ims[1],(W,0));rows.append(r)
S=Image.new('RGB',(2*W,sum(r.height for r in rows)));y=0
for r in rows:S.paste(r,(0,y));y+=r.height
S.save(r'C:\AI\overnight-scratch\fix-worktree\docs\evidence\daytime-2026-10-09\flux-graph\sheet.jpg',quality=80)
