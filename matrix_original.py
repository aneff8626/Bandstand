"""Original Bandstand pilot puzzles. MIT; no MaRs/Raven stimulus artwork used.

Rule families are exploratory, not psychometrically calibrated. Variant siblings
must never appear in the same session. Definitions and rendering are versioned.
"""
import base64
import hashlib

BANK_VERSION='bandstand-matrix-pilot-v1'
FAMILIES=('combine','overlap','difference','count-turn')

def rotate(mask,steps):
    return ((mask<<steps)|(mask>>(4-steps)))&15 if steps else mask

def definitions():
    bank=[]
    for family in FAMILIES:
        for variant in range(3):
            if family=='count-turn':
                cells=[((r+c+variant)%3+1,(r+c*(1 if variant!=1 else 3)+variant)%4) for r in range(3) for c in range(3)]
                correct=cells[-1];n,a=correct
                options=[correct,(n,(a+1)%4),(n%3+1,a),(n%3+1,(a+1)%4)]
                rule='Dot count cycles 1–2–3; the arrow turns one quarter-turn in a consistent direction across each row.'
            else:
                a,b={'combine':([1,4,5],[2,8,10]),'overlap':([3,6,13],[5,10,11]),'difference':([3,5,9],[6,12,10])}[family]
                a=[rotate(v,variant) for v in a];b=[rotate(v,variant) for v in b]
                op={'combine':lambda x,y:x|y,'overlap':lambda x,y:x&y,'difference':lambda x,y:x^y}[family]
                cells=[value for x,y in zip(a,b) for value in (x,y,op(x,y))]
                correct=cells[-1];pool=[a[-1],b[-1],a[-1]|b[-1],a[-1]&b[-1],a[-1]^b[-1],15^correct,1,2,4,8]
                options=[correct]
                for value in pool:
                    if value not in options:options.append(value)
                    if len(options)==4:break
                rule={'combine':'Combine the spokes in the first two cells to produce the third.','overlap':'Keep only spokes present in both of the first two cells.','difference':'Keep spokes present in exactly one of the first two cells.'}[family]
            ident=f'bs-{family}-{variant+1:02d}-v1'
            bank.append(dict(id=ident,family=family,variant=variant,cells=cells,options=options,correct=1,rule=rule,version=BANK_VERSION,license='MIT',calibrated=False))
    return bank

ITEMS=definitions()

def glyph(item,value,x=0,y=0,size=100):
    # Neutral monochrome geometry: color conveys no solution information.
    scale=size/100
    head=f'<g transform="translate({x} {y}) scale({scale})" stroke="#233f57" stroke-width="5" fill="none" stroke-linecap="round">'
    if item['family']=='count-turn':
        count,turn=value
        parts=[f'<g transform="rotate({turn*90} 50 37)"><path d="M50 57V18M37 31L50 18L63 31"/></g>']
        for i in range(count):parts.append(f'<circle cx="{50+(i-(count-1)/2)*17}" cy="80" r="4" fill="#233f57" stroke="none"/>')
    else:
        parts=['<circle cx="50" cy="50" r="7" fill="#233f57" stroke="none"/>']
        for bit,(xx,yy) in enumerate(((50,15),(85,50),(50,85),(15,50))):
            if value&(1<<bit):parts.append(f'<path d="M50 50L{xx} {yy}"/><circle cx="{xx}" cy="{yy}" r="4" fill="#233f57"/>')
    return head+''.join(parts)+'</g>'

def svg(item,option=None):
    if option is not None:return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'+glyph(item,item['options'][option-1])+'</svg>'
    parts=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 330 330"><rect width="330" height="330" fill="#fff"/>']
    for i,value in enumerate(item['cells']):
        x=(i%3)*110;y=(i//3)*110
        parts.append(f'<rect x="{x+4}" y="{y+4}" width="102" height="102" rx="12" fill="#f6f8fb" stroke="#dbe3ea"/>')
        if i==8:parts.append(f'<text x="{x+55}" y="{y+67}" text-anchor="middle" font-family="sans-serif" font-size="38" fill="#8b9aaa">?</text>')
        else:parts.append(glyph(item,value,x+5,y+5))
    return ''.join(parts)+'</svg>'

def image(item,option=None):
    return 'data:image/svg+xml;base64,'+base64.b64encode(svg(item,option).encode()).decode()

def item_hash(item):
    return hashlib.sha256((''.join(svg(item,k) for k in [None,1,2,3,4])).encode()).hexdigest()
