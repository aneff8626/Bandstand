// Real PostgreSQL SQL semantics through PGlite; auth/storage are minimal test fixtures.
// This does NOT test GoTrue, PostgREST, email delivery, or concurrent connections.
// node scripts/check_migrations.mjs /absolute/path/to/pglite/dist/index.js
import {readFile, readdir, mkdir, writeFile} from 'node:fs/promises';
import {pathToFileURL,fileURLToPath} from 'node:url';
import path from 'node:path';
import assert from 'node:assert/strict';
const {PGlite}=await import(pathToFileURL(process.argv[2]).href);
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const results=[];
const a='00000000-0000-4000-8000-000000000001',b='00000000-0000-4000-8000-000000000002';
const rid='10000000-0000-4000-8000-000000000001';
const payload={schema:'bandstand-erp-v1',protocol:'oddball',trials:[{condition:0,times:[-.2,0,.2],channels:{TP9:{accepted:true,wave:[0,1,0]}}}]};
async function scenario(upgrade){
 const db=new PGlite();
 const check=async(name,f)=>{await f();results.push({scenario:upgrade?'upgrade':'fresh',check:name,passed:true});};
 const denied=async(fn,pattern)=>{await assert.rejects(fn,pattern);};
 const user=async(id,role='authenticated')=>{await db.exec('RESET ROLE');await db.query("SELECT set_config('request.jwt.claim.sub',$1,false)",[id]);await db.exec('SET ROLE '+role);};
 const upload=async(id=rid,p=payload)=>db.query('SELECT public.bandstand_upload_erp($1::uuid,$2::jsonb)',[id,JSON.stringify(p)]);
 try{
 await db.exec(`CREATE ROLE anon; CREATE ROLE authenticated; CREATE SCHEMA auth; CREATE SCHEMA storage;
 CREATE TABLE auth.users(id uuid PRIMARY KEY); CREATE TABLE storage.buckets(public boolean);
 CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $$SELECT nullif(current_setting('request.jwt.claim.sub',true),'')::uuid$$;
 GRANT USAGE ON SCHEMA public,auth TO anon,authenticated;
 INSERT INTO auth.users VALUES('${a}'),('${b}');`);
 const names=(await readdir(path.join(root,'supabase/migrations'))).filter(x=>x.endsWith('.sql')).sort();
 for(let i=0;i<names.length;i++){
  await db.exec(await readFile(path.join(root,'supabase/migrations',names[i]),'utf8'));
  if(upgrade&&i===2){await user(a);await db.exec('SELECT bandstand_set_erp_consent(true)');await upload();await db.exec('RESET ROLE');}
 }
 await check('ordered migrations and permission inventory',async()=>{
  const reports=await db.exec(await readFile(path.join(root,'supabase/checks/verify_permissions.sql'),'utf8'));
  const rows=reports.flatMap(x=>x.rows);assert.ok(rows.length>30);assert.deepEqual(rows.filter(x=>x.ok!==true),[]);
 });
 if(upgrade)await check('pre-upgrade ERP remains intact',async()=>{const r=await db.query('SELECT payload FROM bandstand_erp_recordings');assert.deepEqual(r.rows[0].payload,payload);});
 await user(b,'anon');
 await check('anonymous RPC refused',()=>denied(()=>db.exec('SELECT bandstand_list_erp()'),/permission denied/));
 await user(b);
 await check('upload requires consent',()=>denied(()=>upload(),/consent required/));
 await check('direct reads and writes refused',async()=>{
  await denied(()=>db.exec('SELECT * FROM bandstand_erp_recordings'),/permission denied/);
  await denied(()=>db.exec('DELETE FROM bandstand_consent'),/permission denied/);
 });
 await db.exec('SELECT bandstand_set_erp_consent(true)');await upload();
 await check('retry is idempotent',async()=>{await upload();assert.equal((await db.exec('SELECT * FROM bandstand_list_erp()'))[0].rows.length,1);});
 await check('private text injection rejected',()=>denied(()=>upload(rid,{...payload,text:'SYNTHETIC PRIVATE CANARY'}),/Invalid ERP/));
 await check('malformed wave rejected',async()=>{
  const bad=structuredClone(payload);bad.trials[0].channels.TP9.wave=['invalid'];await denied(()=>upload(rid,bad),/Invalid ERP/);
 });
 await check('v2 metadata accepted; unknown fields and free-text rejections refused',async()=>{
  const v2=structuredClone(payload);v2.schema='bandstand-erp-v2';
  v2.trials[0].channels.TP9.rejection=[];
  v2.recording={app_version:'0.3.0',sample_rate_hz:256,units:'uV',reference:'FPz',channels:['TP9'],preprocessing:'causal-hp0.1-lp30-notch60q30',grid:'interpolated-256hz',epoch_s:[-.2,.8],baseline_s:[-.2,0],analysis_window_s:[.3,.5],trials_planned:1,trials_presented:1,end:'completed'};
  await upload(rid,v2); // validated before the idempotent insert
  v2.recording.subject_name='SYNTHETIC';await denied(()=>upload(rid,v2),/Invalid ERP/);delete v2.recording.subject_name;
  v2.trials[0].channels.TP9.rejection=['SYNTHETIC TEXT'];await denied(()=>upload(rid,v2),/Invalid ERP/);
 });
 await user(a);await db.exec('SELECT bandstand_set_erp_consent(true)');await upload();
 await check('same recording ID isolated by account',async()=>{assert.equal((await db.exec('SELECT * FROM bandstand_list_erp()'))[0].rows.length,1);});
 await check('withdrawal immediately blocks uploads',async()=>{
  await db.exec('SELECT bandstand_set_erp_consent(false)');await denied(()=>upload(),/consent required/);
 });
 await db.exec('SELECT bandstand_set_erp_consent(true)');
 await db.exec('RESET ROLE');
 await check('decoder uploads remain prohibited',()=>denied(()=>db.exec(`UPDATE bandstand_consent SET decoder_sharing=true WHERE user_id='${a}'`),/check constraint/));
 await db.query(`INSERT INTO bandstand_erp_recordings(user_id,recording_id,payload)
 SELECT $1::uuid,gen_random_uuid(),$2::jsonb FROM generate_series(1,99)`,[a,JSON.stringify(payload)]);
 await user(a);
 await check('daily quota enforced; retry remains allowed',async()=>{
  await denied(()=>upload('10000000-0000-4000-8000-000000000002'),/daily limit/);await upload();
 });
 await db.exec('RESET ROLE');
 await db.exec(`UPDATE bandstand_erp_recordings SET created_at=now()-interval '2 days' WHERE user_id='${a}'`);
 await db.query(`INSERT INTO bandstand_erp_recordings(user_id,recording_id,payload,created_at)
 SELECT $1::uuid,gen_random_uuid(),$2::jsonb,now()-interval '2 days' FROM generate_series(1,1900)`,[a,JSON.stringify(payload)]);
 await user(a);
 await check('total quota enforced',()=>denied(()=>upload('10000000-0000-4000-8000-000000000003'),/storage limit/));
 await check('delete ERP affects caller only',async()=>{
  await db.exec('SELECT bandstand_delete_erp()');assert.equal((await db.exec('SELECT * FROM bandstand_list_erp()'))[0].rows.length,0);
  await user(b);assert.equal((await db.exec('SELECT * FROM bandstand_list_erp()'))[0].rows.length,1);
 });
 await check('account deletion cascades without deleting other account',async()=>{
  await db.exec('SELECT bandstand_delete_own_account()');await db.exec('RESET ROLE');
  assert.equal((await db.query('SELECT count(*)::int AS n FROM auth.users WHERE id=$1',[b])).rows[0].n,0);
  assert.equal((await db.query('SELECT count(*)::int AS n FROM auth.users WHERE id=$1',[a])).rows[0].n,1);
  assert.equal((await db.exec('SELECT count(*)::int AS n FROM bandstand_erp_recordings'))[0].rows[0].n,0);
 });
 }finally{await db.close();}
}
await scenario(false);await scenario(true);
await mkdir(path.join(root,'.audit'),{recursive:true});
await writeFile(path.join(root,'.audit/migrations.json'),JSON.stringify({engine:'PGlite PostgreSQL',limitations:['auth/storage fixtures, not live Supabase','single connection; concurrency untested'],results},null,2));
console.log(`${results.length} SQL migration checks passed (fresh and upgrade). Live API/auth and concurrency untested.`);
