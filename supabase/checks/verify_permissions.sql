-- Read-only permission inventory for the Bandstand schema. Changes nothing.
-- Run locally with scripts/staging_accounts.py, or paste into the Supabase SQL editor of a
-- development, staging or production project and compare. Every row should have ok = true.
WITH tables(name) AS (VALUES ('bandstand_consent'),('bandstand_model_releases'),('bandstand_erp_recordings')),
client_rpcs(sig) AS (VALUES ('bandstand_delete_own_account()'),('bandstand_set_erp_consent(boolean)'),('bandstand_upload_erp(uuid,jsonb)'),
 ('bandstand_delete_erp()'),('bandstand_sharing_status()'),('bandstand_list_erp()')),
internal_fns(sig) AS (VALUES ('bandstand_valid_erp(jsonb)')),
fns AS (SELECT p.oid,p.proname||'('||pg_get_function_identity_arguments(p.oid)||')' AS label,p.prosecdef,p.proconfig,pg_get_userbyid(p.proowner) AS owner
 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' AND p.proname LIKE 'bandstand\_%'),
roles(r) AS (VALUES ('anon'),('authenticated'))
SELECT 'table exists' AS check_name,t.name AS object,to_regclass('public.'||t.name) IS NOT NULL AS ok,'' AS detail FROM tables t
UNION ALL
SELECT 'row level security enabled',t.name,COALESCE(c.relrowsecurity,false),'' FROM tables t LEFT JOIN pg_class c ON c.oid=to_regclass('public.'||t.name)
UNION ALL
SELECT 'no direct table privilege for '||r.r,t.name,
 NOT (has_table_privilege(r.r,to_regclass('public.'||t.name),'SELECT') OR has_table_privilege(r.r,to_regclass('public.'||t.name),'INSERT')
  OR has_table_privilege(r.r,to_regclass('public.'||t.name),'UPDATE') OR has_table_privilege(r.r,to_regclass('public.'||t.name),'DELETE')
  OR has_table_privilege(r.r,to_regclass('public.'||t.name),'TRUNCATE') OR has_table_privilege(r.r,to_regclass('public.'||t.name),'REFERENCES')),''
 FROM tables t CROSS JOIN roles r WHERE to_regclass('public.'||t.name) IS NOT NULL
UNION ALL
SELECT 'no row policies (access is RPC-only)',t.name,NOT EXISTS(SELECT 1 FROM pg_policies p WHERE p.schemaname='public' AND p.tablename=t.name),
 COALESCE((SELECT string_agg(policyname,', ') FROM pg_policies p WHERE p.schemaname='public' AND p.tablename=t.name),'') FROM tables t
UNION ALL
SELECT 'expected function present',c.sig,to_regprocedure('public.'||c.sig) IS NOT NULL,'' FROM (SELECT sig FROM client_rpcs UNION ALL SELECT sig FROM internal_fns) c
UNION ALL
SELECT 'client RPC is SECURITY DEFINER with empty search_path',f.label,f.prosecdef AND f.proconfig @> ARRAY['search_path=""'],
 'owner='||f.owner||' config='||COALESCE(array_to_string(f.proconfig,';'),'none') FROM fns f WHERE f.label NOT LIKE 'bandstand_valid_erp%'
UNION ALL
SELECT 'internal validator is not SECURITY DEFINER and pins search_path',f.label,NOT f.prosecdef AND f.proconfig @> ARRAY['search_path=""'],'' FROM fns f WHERE f.label LIKE 'bandstand_valid_erp%'
UNION ALL
SELECT 'anon cannot execute',f.label,NOT has_function_privilege('anon',f.oid,'EXECUTE'),'' FROM fns f
UNION ALL
SELECT 'authenticated '||CASE WHEN f.label LIKE 'bandstand_valid_erp%' THEN 'cannot' ELSE 'can' END||' execute',f.label,
 has_function_privilege('authenticated',f.oid,'EXECUTE')=(f.label NOT LIKE 'bandstand_valid_erp%'),'' FROM fns f
UNION ALL
SELECT 'PUBLIC has no execute grant',f.label,NOT EXISTS(SELECT 1 FROM pg_proc p,aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) a WHERE p.oid=f.oid AND a.grantee=0 AND a.privilege_type='EXECUTE'),'' FROM fns f
UNION ALL
SELECT 'auth-user deletion cascades',c.conrelid::regclass::text,c.confdeltype='c',pg_get_constraintdef(c.oid)
 FROM pg_constraint c WHERE c.contype='f' AND c.confrelid='auth.users'::regclass AND c.conrelid::regclass::text LIKE '%bandstand\_%'
UNION ALL
SELECT 'decoder sharing constrained false','bandstand_consent',EXISTS(SELECT 1 FROM pg_constraint c WHERE c.conrelid=to_regclass('public.bandstand_consent') AND c.contype='c' AND pg_get_constraintdef(c.oid) LIKE '%decoder_sharing = false%'),''
UNION ALL
SELECT 'no public storage bucket','storage.buckets',
 CASE WHEN to_regclass('storage.buckets') IS NULL THEN true ELSE NOT EXISTS(SELECT 1 FROM storage.buckets WHERE public) END,
 CASE WHEN to_regclass('storage.buckets') IS NULL THEN 'storage schema absent' ELSE '' END
UNION ALL
SELECT 'rls_auto_enable() not callable by clients','public.rls_auto_enable()',
 CASE WHEN to_regprocedure('public.rls_auto_enable()') IS NULL THEN true
  ELSE NOT has_function_privilege('anon','public.rls_auto_enable()','EXECUTE') AND NOT has_function_privilege('authenticated','public.rls_auto_enable()','EXECUTE') END,
 CASE WHEN to_regprocedure('public.rls_auto_enable()') IS NULL THEN 'function absent on this project' ELSE 'function present' END
ORDER BY 1,2;
