"""Render an original-item mockup as SVG; no third-party stimulus artwork."""
from pathlib import Path
import sys,math
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from matrix_original import ITEMS,svg,glyph
item=next(v for v in ITEMS if v['id']=='bs-count-turn-01-v1')
out=Path(sys.argv[1]);out.parent.mkdir(parents=True,exist_ok=True)
p=['<svg xmlns="http://www.w3.org/2000/svg" width="1140" height="760" viewBox="0 0 1140 760"><rect width="1140" height="760" rx="20" fill="#f5f7fb"/>', '<style>text{font-family:Arial,sans-serif;fill:#233f57}.muted{fill:#70869a}.small{font-size:14px}</style>', '<text x="44" y="48" font-size="19" font-weight="bold">BANDSTAND</text><text x="44" y="94" font-size="30" font-weight="bold">What completes the pattern?</text><text x="44" y="124" class="small muted">Original pilot item · example only · not calibrated</text><line x1="668" y1="155" x2="668" y2="704" stroke="#d9e2ec"/>']
p.append('<g transform="translate(140 155) scale(1.15)">'+svg(item).split('>',1)[1].rsplit('</svg>',1)[0]+'</g>')
for j,k in enumerate([2,4,1,3]):
 x=44+j*150;y=562
 p.append(f'<rect x="{x}" y="{y}" width="132" height="144" rx="12" fill="white" stroke="#cad7e3"/>'+glyph(item,item['options'][k-1],x+16,y+7)+f'<text x="{x+66}" y="{y+128}" text-anchor="middle" font-size="16">{"ABCD"[j]}</text>')
p.extend(['<text x="706" y="188" font-size="22" font-weight="bold">Reasoning percentile</text>','<text x="706" y="218" class="small muted">Illustrative result · research reference</text>','<text x="706" y="276" font-size="34" font-weight="bold" style="fill:#416c96">72nd percentile</text>','<text x="706" y="307" class="small muted">95% credible range: 45–88</text>'])
x=lambda z:710+(z+3)*61;y=lambda z:485-115*math.exp(-z*z/2)
points=[(z/30,x(z/30),y(z/30)) for z in range(-90,91)]
def area(a):return f'M{a[0][1]},485 '+' '.join(f'L{v[1]},{v[2]}' for v in a)+f' L{a[-1][1]},485 Z'
p.append(f'<path d="{area(points)}" fill="#e0e8f1"/>')
a=[v for v in points if v[0]<=.58];p.append(f'<path d="{area(a)}" fill="#8aabc9"/>')
p.append(f'<line x1="{x(.58)}" x2="{x(.58)}" y1="347" y2="485" stroke="#416c96" stroke-width="3"/>')
for z,t in [(-2,'2'),(-1,'16'),(0,'50'),(1,'84'),(2,'98')]:p.append(f'<text x="{x(z)}" y="511" text-anchor="middle" class="small muted">{t}</text>')
p.extend(['<text x="893" y="539" text-anchor="middle" class="small muted">Reference percentile · model distribution</text>',f'<rect x="{x(-.126)}" y="562" width="{x(1.175)-x(-.126)}" height="10" rx="5" fill="#a7bed4"/>',f'<circle cx="{x(.58)}" cy="567" r="6" fill="#416c96"/>','<text x="706" y="620" class="small muted">Pilot answers are saved separately.</text>','<text x="706" y="643" class="small muted">They do not affect today’s percentile.</text>','<text x="44" y="738" font-size="12" class="muted">Mockup · original Bandstand geometry · displayed percentile is fictional</text></svg>'])
out.write_text(''.join(p));print(out)
