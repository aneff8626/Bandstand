"""Download only the pinned public encoder; verify upstream Git/LFS hashes."""
import hashlib,json,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REVISION='1110a243fdf4706b3f48f1d95db1a4f5529b4d41'
REPO='sentence-transformers/all-MiniLM-L6-v2'
FILES=('vocab.txt','README.md','tokenizer.json','config.json','special_tokens_map.json','tokenizer_config.json','model.safetensors')
def fetch(url):
 with urllib.request.urlopen(url,timeout=120) as response:return response.read()
def main():
 root=ROOT/'models/all-MiniLM-L6-v2';root.mkdir(parents=True,exist_ok=True)
 info=json.loads(fetch('https://huggingface.co/api/models/'+REPO+'/revision/'+REVISION+'?blobs=true'));manifest={}
 for name in FILES:
  data=fetch('https://huggingface.co/'+REPO+'/resolve/'+REVISION+'/'+name)
  item=next(x for x in info['siblings'] if x['rfilename']==name)
  expected=item['lfs']['sha256'] if item.get('lfs') else item['blobId']
  actual=hashlib.sha256(data).hexdigest() if item.get('lfs') else hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
  if actual!=expected:raise ValueError('Upstream hash mismatch: '+name)
  (root/name).write_bytes(data);manifest[name]=hashlib.sha256(data).hexdigest()
 for name,data in [('LICENSE',fetch('https://www.apache.org/licenses/LICENSE-2.0.txt')),('revision.txt',REVISION.encode())]:
  (root/name).write_bytes(data);manifest[name]=hashlib.sha256(data).hexdigest()
 (root/'public-manifest.json').write_text(json.dumps(manifest,indent=2))
 print('Public encoder verified. No participant data included.')
if __name__=='__main__':main()
