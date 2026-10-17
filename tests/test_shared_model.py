import contextlib,hashlib,io,json,logging,secrets,struct,tempfile,threading,time,unittest
from pathlib import Path
import numpy as np
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from cumulative_semantic import connect,blob,SCHEMA
import shared_model,shared_learning
F=6
def keypair():
 k=Ed25519PrivateKey.generate();return k,k.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw).hex()
def model(seed=0):
 r=np.random.default_rng(seed);return r.normal(size=F),r.uniform(.5,2,size=F),r.normal(scale=.1,size=(F+1,384))
def manifest(**k):return {'feature_schema':SCHEMA,'model_family':shared_model.FAMILY,'encoder':shared_model.ENCODER,'round_id':'round-1','parent_model_sha256':'b'*64,'learning_rate':.05,'clip_norm':.5,**k}
def archive(root,n=40,canary='',seed=1,order=None):
 db=connect(root);r=np.random.default_rng(seed);rows=[]
 for i in range(n):
  y=r.normal(size=384);y/=np.linalg.norm(y)
  rows.append((f'{i:04d}','s',float(i),float(i)+1,f'{canary} private phrase {i}',f'{canary} previous',blob(r.normal(size=F)),blob(np.ones(F)),blob(y),blob(np.zeros(384))))
 for row in (rows if order is None else [rows[i] for i in order]):db.execute('INSERT INTO examples VALUES (?,?,?,?,?,?,?,?,?,?)',row)
 db.commit();return db

class ReleaseTests(unittest.TestCase):
 def setUp(self):self.key,self.pub=keypair();self.body=shared_model.pack('1.0.0',*model(),parent='',evaluation={'held_out_participants':12},privacy={'epsilon':4.0,'delta':1e-6})
 def signed(self,body=None):return shared_model.sign(body or self.body,self.key)
 def test_round_trip_and_no_trust_by_default(self):
  header,arrays=shared_model.verify(self.signed(),(self.pub,))
  self.assertEqual(header['version'],'1.0.0');self.assertEqual(arrays['weights'].shape,(F+1,384))
  np.testing.assert_allclose(arrays['mean'],model()[0].astype('f'))
  self.assertEqual(shared_model.TRUSTED_KEYS,())
  with self.assertRaises(ValueError):shared_model.verify(self.signed())
 def test_refuses_tampering_wrong_key_and_foreign_formats(self):
  data=bytearray(self.signed());data[100]^=1
  _,other=keypair();bad=[bytes(data),b'\x80\x04pickle'+bytes(100),self.signed()[:-1]]
  for item in bad:
   with self.subTest(item=item[:12]),self.assertRaises(ValueError):shared_model.verify(item,(self.pub,))
  with self.assertRaises(ValueError):shared_model.verify(self.signed(),(other,))
 def rebuilt(self,change):
  (n,)=struct.unpack('<I',self.body[4:8]);header=json.loads(self.body[8:8+n]);tensors=self.body[8+n:];tensors=change(header,tensors) or tensors
  raw=json.dumps(header).encode();return shared_model.sign(b'BSM1'+struct.pack('<I',len(raw))+raw+tensors,self.key)
 def test_refuses_validly_signed_but_wrong_contents(self):
  w=shared_model.shapes(F)['weights']
  cases={'other encoder':lambda h,t:h.update(encoder={**shared_model.ENCODER,'revision':'0'*40}),'other schema':lambda h,t:h.update(feature_schema='other'),
   'extra field':lambda h,t:h.update(notes='text'),'text metadata':lambda h,t:h.update(privacy={'epsilon':'four'}),'wrong shape':lambda h,t:h['tensors'][2].update(shape=[w[0],383]),
   'trailing bytes':lambda h,t:t+b'\0\0\0\0','hash mismatch':lambda h,t:h['tensors'][0].update(sha256='0'*64),
   'nonfinite':lambda h,t:(lambda v:(h['tensors'][0].update(sha256=hashlib.sha256(v).hexdigest()),v+t[F*4:])[1])(np.full(F,np.nan,'<f4').tobytes())}
  for name,change in cases.items():
   with self.subTest(name),self.assertRaises(ValueError):shared_model.verify(self.rebuilt(change),(self.pub,))
 def test_install_keeps_last_good_and_rolls_back(self):
  with tempfile.TemporaryDirectory() as root:
   first=self.signed();second=shared_model.sign(shared_model.pack('1.0.1',*model(1)),self.key)
   shared_model.install(root,first,(self.pub,));shared_model.install(root,second,(self.pub,))
   self.assertEqual(shared_model.current(root,(self.pub,))[0]['version'],'1.0.1')
   with self.assertRaises(ValueError):shared_model.install(root,b'BSM1'+bytes(200),(self.pub,))
   self.assertEqual(shared_model.current(root,(self.pub,))[0]['version'],'1.0.1')
   folder=Path(root)/'shared-models';state=json.loads((folder/'state.json').read_text());(folder/(state['current']+'.bsm')).write_bytes(b'corrupt'*20)
   self.assertEqual(shared_model.current(root,(self.pub,))[0]['version'],'1.0.0')  # falls back to last good
   shared_model.rollback(root);self.assertEqual(shared_model.current(root,(self.pub,))[0]['version'],'1.0.0')
 def test_encoder_pin_matches_the_download_script(self):
  src=(Path(__file__).parents[1]/'scripts/prepare_public_model.py').read_text()
  self.assertIn(shared_model.ENCODER['revision'],src);self.assertIn(shared_model.ENCODER['repo'],src)

class ContributionTests(unittest.TestCase):
 def test_canaries_never_leave_in_contribution_logs_or_output(self):
  canary='CANARY-'+secrets.token_hex(8)
  with tempfile.TemporaryDirectory() as root:
   db=archive(root,canary=canary);log=io.StringIO();handler=logging.StreamHandler(log);logging.getLogger().addHandler(handler)
   out=io.StringIO()
   try:
    with contextlib.redirect_stdout(out),contextlib.redirect_stderr(out):
     update=shared_learning.local_round_update(db,manifest(),*model(),consent=True);data=shared_learning.contribution(update,.5)
   finally:logging.getLogger().removeHandler(handler);db.close()
   for where,text in (('contribution',data),('logs',log.getvalue().encode()),('output',out.getvalue().encode()),('header',data[8:8+struct.unpack('<I',data[4:8])[0]])):
    self.assertNotIn(canary.encode(),text,where);self.assertNotIn(b'private phrase',text,where)
   header=json.loads(data[8:8+struct.unpack('<I',data[4:8])[0]]);self.assertEqual(set(header),{'format','round_id','parent_model_sha256','shape','sha256'})
 def test_same_data_gives_identical_contributions_on_two_clients(self):
  with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
   da=archive(a);db=archive(b,order=list(reversed(range(40))))
   ca=shared_learning.contribution(shared_learning.local_round_update(da,manifest(),*model(),consent=True),.5)
   cb=shared_learning.contribution(shared_learning.local_round_update(db,manifest(),*model(),consent=True),.5)
   da.close();db.close();self.assertEqual(ca,cb)
 def test_coordinator_checks_round_shape_norm_and_hash(self):
  with tempfile.TemporaryDirectory() as root:
   d=archive(root);data=shared_learning.contribution(shared_learning.local_round_update(d,manifest(),*model(),consent=True),.5);d.close()
  delta=shared_learning.read_contribution(data,manifest(),F);self.assertLessEqual(np.linalg.norm(delta),.5001)
  tampered=bytearray(data);tampered[-1]^=1
  for name,args in {'other round':(data,manifest(round_id='round-2'),F),'other parent':(data,manifest(parent_model_sha256='c'*64),F),'other shape':(data,manifest(),F+1),'tampered':(bytes(tampered),manifest(),F),'garbage':(b'BSC1'+bytes(40),manifest(),F)}.items():
   with self.subTest(name),self.assertRaises(ValueError):shared_learning.read_contribution(*args)
  big={'delta':np.ones((F+1,384),'f'),'round_id':'round-1','parent_model_sha256':'b'*64}
  with self.assertRaises(ValueError):shared_learning.contribution(big,.5)
  with self.assertRaises(ValueError):shared_learning.contribution({**big,'delta':np.full((F+1,384),np.nan,'f')},1e9)
 def test_encoder_mismatch_and_consent_required(self):
  with tempfile.TemporaryDirectory() as root:
   d=archive(root)
   with self.assertRaises(ValueError):shared_learning.local_round_update(d,manifest(encoder={**shared_model.ENCODER,'revision':'x'}),*model(),consent=True)
   with self.assertRaises(PermissionError):shared_learning.local_round_update(d,manifest(),*model())
   d.close()
  with self.assertRaises(PermissionError):shared_learning.train_isolated('/nonexistent',manifest(),model())
 def test_isolated_training_keeps_the_main_loop_responsive(self):
  with tempfile.TemporaryDirectory() as root:
   archive(root,n=3000).close();ticks=[];stop=threading.Event()
   def acquisition():
    while not stop.is_set():ticks.append(time.monotonic());time.sleep(.01)
   t=threading.Thread(target=acquisition);t.start()
   try:data=shared_learning.train_isolated(root,manifest(),model(),consent=True,timeout=120)
   finally:stop.set();t.join()
   self.assertEqual(shared_learning.read_contribution(data,manifest(),F).shape,(F+1,384))
   self.assertLess(max(np.diff(ticks)),.25,'acquisition loop stalled during training')
