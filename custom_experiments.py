"""Local custom experiment design and bounded, decoded media imports."""
import base64, hashlib, io, math, re, wave
from PIL import Image, ImageOps
from private_storage import DATA_ROOT

def import_media(body):
 raw=base64.b64decode(body.get('data',''),validate=True)
 if not 0<len(raw)<=12*1024*1024:raise ValueError('Use files smaller than 12 MB')
 kind=body.get('kind')
 if kind=='image':
  with Image.open(io.BytesIO(raw)) as im:
   if im.width*im.height>16000000:raise ValueError('Image exceeds 16 megapixels')
   im=ImageOps.exif_transpose(im).convert('RGB');im.thumbnail((1600,1600));out=io.BytesIO();im.save(out,format='PNG');raw=out.getvalue()
  ext='png'
 elif kind=='audio':
  with wave.open(io.BytesIO(raw)) as wav:
   if wav.getcomptype()!='NONE' or wav.getnchannels() not in (1,2) or wav.getsampwidth() not in (1,2,3,4) or not 8000<=wav.getframerate()<=192000 or not 0<wav.getnframes()/wav.getframerate()<=30:raise ValueError('Use PCM WAV audio, mono/stereo, up to 30 seconds')
  ext='wav'
 else:raise ValueError('Choose an image or PCM WAV audio; video is not supported')
 name='custom-'+hashlib.sha256(raw).hexdigest()+'.'+ext
 directory=DATA_ROOT/'stimuli';directory.mkdir(parents=True,exist_ok=True);(directory/name).write_bytes(raw)
 return dict(file=name,kind=kind)

def validate_design(cfg,mode):
 d=cfg.get('custom_design') or {};names=d.get('conditions',cfg.get('conditions',[]))
 if not isinstance(names,list) or not 2<=len(names)<=4 or any(not isinstance(n,str) or not n.strip() or len(n)>80 for n in names):raise ValueError('Name 2–4 conditions')
 names=[n.strip() for n in names]
 if len(set(names))!=len(names):raise ValueError('Condition names must be different')
 instructions=d.get('instructions',['']*len(names))
 if not isinstance(instructions,list) or len(instructions)!=len(names) or any(not isinstance(x,str) or len(x)>500 for x in instructions):raise ValueError('Instructions must be at most 500 characters per condition')
 def number(key,default,lo,hi):
  value=d.get(key,default)
  if type(value) not in (int,float) or not math.isfinite(value) or not lo<=value<=hi:raise ValueError('Invalid '+key.replace('_',' '))
  return value
 duration=number('duration_ms',12000 if mode=='tf' else 800,6000 if mode=='tf' else 50,120000 if mode=='tf' else 30000)
 interval=number('interval_ms',2000 if mode=='tf' else 1200,0 if mode=='tf' else 200,60000)
 repeats=number('repetitions',10 if mode=='tf' else 20,1,250)
 if int(repeats)!=repeats:raise ValueError('Repetitions must be a whole number')
 order=d.get('order','alternating' if mode=='tf' else 'randomized')
 if order not in ('alternating','randomized','custom'):raise ValueError('Unknown order')
 sequence=d.get('sequence',list(range(len(names))))
 if order=='custom' and (not isinstance(sequence,list) or sorted(sequence)!=list(range(len(names))) or any(type(n)!=int for n in sequence)):raise ValueError('Custom order must include each condition number exactly once')
 responses=d.get('responses',[])
 if not isinstance(responses,list) or len(responses)>8:raise ValueError('Use at most eight response keys')
 keys=[]
 for response in responses:
  if not isinstance(response,dict):raise ValueError('Invalid response key')
  key=response.get('key','');meaning=response.get('meaning','')
  if not isinstance(key,str) or not (len(key)==1 or key in ('ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Enter')) or not isinstance(meaning,str) or not meaning.strip() or len(meaning)>80 or key.lower() in keys:raise ValueError('Give each response a unique key and a meaning (Escape is reserved)')
  keys.append(key.lower())
 media=d.get('media',[[] for _ in names])
 if mode=='erp':
  if not isinstance(media,list) or len(media)!=len(names):raise ValueError('Add media for each condition')
  for pool in media:
   if not isinstance(pool,list) or not 1<=len(pool)<=100:raise ValueError('Add 1–100 files for every condition')
   for name in pool:
    if not isinstance(name,str) or not re.fullmatch(r'custom-[a-f0-9]{64}\.(png|wav)',name) or not (DATA_ROOT/'stimuli'/name).is_file():raise ValueError('A stimulus file is missing; import it again')
 return dict(conditions=names,instructions=instructions,duration_ms=round(duration),interval_ms=round(interval),repetitions=int(repeats),order=order,sequence=sequence,responses=responses,media=media,break_every=int(number('break_every',0,0,1000)),break_ms=number('break_ms',10000,0,120000))

def condition_order(design,rng):
 labels=(design['sequence'] if design['order']=='custom' else list(range(len(design['conditions']))))*design['repetitions']
 if design['order']=='randomized':rng.shuffle(labels)
 return labels
