-- ERP payload schema v2 (adds allowlisted recording metadata) and provisional per-user upload quotas.
-- v1 payloads remain valid. The client keeps sending v1 until the ERP sharing notice lists the v2 fields.
-- CPU per request is bounded by the API roles' statement timeout (Supabase default 8 s for authenticated).
BEGIN;
CREATE OR REPLACE FUNCTION public.bandstand_valid_erp(recording jsonb)
RETURNS boolean LANGUAGE plpgsql IMMUTABLE SET search_path='' AS $$
DECLARE t jsonb; ch record; n jsonb; r jsonb; v2 boolean; k text;
BEGIN
 IF recording IS NULL OR jsonb_typeof(recording) IS DISTINCT FROM 'object' OR COALESCE(recording->>'schema','') NOT IN ('bandstand-erp-v1','bandstand-erp-v2')
 OR jsonb_typeof(recording->'schema') IS DISTINCT FROM 'string'
 OR COALESCE(recording->>'protocol','') NOT IN ('oddball','auditory','flanker','reward')
 OR jsonb_typeof(recording->'trials') IS DISTINCT FROM 'array' THEN RETURN false; END IF;
 v2 := recording->>'schema'='bandstand-erp-v2';
 IF (recording - CASE WHEN v2 THEN ARRAY['schema','protocol','trials','recording'] ELSE ARRAY['schema','protocol','trials'] END) <> '{}'::jsonb THEN RETURN false; END IF;
 IF jsonb_array_length(recording->'trials') NOT BETWEEN 1 AND 10000 OR octet_length(recording::text)>10000000 THEN RETURN false; END IF;
 IF v2 THEN
  r := recording->'recording';
  IF jsonb_typeof(r) IS DISTINCT FROM 'object'
   OR (r - ARRAY['app_version','sample_rate_hz','units','reference','channels','preprocessing','grid','epoch_s','baseline_s','analysis_window_s','trials_planned','trials_presented','end'])<>'{}'::jsonb
   OR (SELECT count(*) FROM jsonb_object_keys(r))<>13 THEN RETURN false; END IF;
  IF jsonb_typeof(r->'app_version') IS DISTINCT FROM 'string' OR (r->>'app_version') !~ '^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}(-[a-z0-9.]{1,20})?$'
   OR r->'sample_rate_hz' IS DISTINCT FROM '256'::jsonb OR r->'units' IS DISTINCT FROM '"uV"'::jsonb
   OR r->'reference' NOT IN ('"FPz"'::jsonb,'"TP9-TP10-mean"'::jsonb)
   OR r->'preprocessing' IS DISTINCT FROM '"causal-hp0.1-lp30-notch60q30"'::jsonb OR r->'grid' IS DISTINCT FROM '"interpolated-256hz"'::jsonb
   OR r->'end' NOT IN ('"completed"'::jsonb,'"stopped"'::jsonb,'"interrupted"'::jsonb)
   OR jsonb_typeof(r->'channels') IS DISTINCT FROM 'array' OR jsonb_array_length(r->'channels') NOT BETWEEN 1 AND 4 THEN RETURN false; END IF;
  FOR n IN SELECT value FROM jsonb_array_elements(r->'channels') LOOP
   IF n NOT IN ('"TP9"'::jsonb,'"AF7"'::jsonb,'"AF8"'::jsonb,'"TP10"'::jsonb) THEN RETURN false; END IF;
  END LOOP;
  FOREACH k IN ARRAY ARRAY['epoch_s','baseline_s','analysis_window_s'] LOOP
   IF jsonb_typeof(r->k) IS DISTINCT FROM 'array' OR jsonb_array_length(r->k)<>2 OR jsonb_typeof(r->k->0) IS DISTINCT FROM 'number' OR jsonb_typeof(r->k->1) IS DISTINCT FROM 'number'
    OR (r->k->>0)::numeric NOT BETWEEN -10 AND 10 OR (r->k->>1)::numeric NOT BETWEEN -10 AND 10 OR (r->k->>0)::numeric>(r->k->>1)::numeric THEN RETURN false; END IF;
  END LOOP;
  FOREACH k IN ARRAY ARRAY['trials_planned','trials_presented'] LOOP
   IF jsonb_typeof(r->k) IS DISTINCT FROM 'number' OR (r->>k)::numeric<>trunc((r->>k)::numeric) OR (r->>k)::numeric NOT BETWEEN 1 AND 10000 THEN RETURN false; END IF;
  END LOOP;
  IF (r->>'trials_presented')::int<>jsonb_array_length(recording->'trials') THEN RETURN false; END IF;
 END IF;
 FOR t IN SELECT value FROM jsonb_array_elements(recording->'trials') LOOP
  IF jsonb_typeof(t) IS DISTINCT FROM 'object' OR (t - ARRAY['condition','times','channels'])<>'{}'::jsonb OR COALESCE(t->>'condition','') NOT IN ('0','1') OR jsonb_typeof(t->'condition') IS DISTINCT FROM 'number'
   OR jsonb_typeof(t->'times') IS DISTINCT FROM 'array' OR jsonb_typeof(t->'channels') IS DISTINCT FROM 'object' THEN RETURN false; END IF;
  IF jsonb_array_length(t->'times') NOT BETWEEN 1 AND 1024 THEN RETURN false; END IF;
  FOR n IN SELECT value FROM jsonb_array_elements(t->'times') LOOP
   IF jsonb_typeof(n) IS DISTINCT FROM 'number' OR (n::text)::numeric NOT BETWEEN -10 AND 10 THEN RETURN false; END IF;
  END LOOP;
  FOR ch IN SELECT * FROM jsonb_each(t->'channels') LOOP
   IF ch.key NOT IN ('TP9','AF7','AF8','TP10') OR jsonb_typeof(ch.value) IS DISTINCT FROM 'object'
    OR (ch.value - CASE WHEN v2 THEN ARRAY['accepted','wave','rejection'] ELSE ARRAY['accepted','wave'] END)<>'{}'::jsonb
    OR jsonb_typeof(ch.value->'accepted') IS DISTINCT FROM 'boolean' THEN RETURN false; END IF;
   IF v2 THEN
    IF jsonb_typeof(ch.value->'rejection') IS DISTINCT FROM 'array' OR jsonb_array_length(ch.value->'rejection')>8 THEN RETURN false; END IF;
    FOR n IN SELECT value FROM jsonb_array_elements(ch.value->'rejection') LOOP
     IF n NOT IN ('"missing"'::jsonb,'"clipping"'::jsonb,'"flatline"'::jsonb,'"transient"'::jsonb,'"blink"'::jsonb,'"muscle"'::jsonb,'"timing"'::jsonb,'"other"'::jsonb) THEN RETURN false; END IF;
    END LOOP;
   END IF;
   IF ch.value->'wave' IS NULL THEN RETURN false; END IF;
   IF ch.value->'wave'<>'null'::jsonb THEN
    IF jsonb_typeof(ch.value->'wave') IS DISTINCT FROM 'array' THEN RETURN false; END IF;
    IF jsonb_array_length(ch.value->'wave')<>jsonb_array_length(t->'times') THEN RETURN false; END IF;
    FOR n IN SELECT value FROM jsonb_array_elements(ch.value->'wave') LOOP
     IF jsonb_typeof(n) IS DISTINCT FROM 'number' OR (n::text)::numeric NOT BETWEEN -1000000 AND 1000000 THEN RETURN false; END IF;
    END LOOP;
   END IF;
  END LOOP;
 END LOOP;
 RETURN true;
EXCEPTION WHEN OTHERS THEN RETURN false;
END; $$;
REVOKE ALL ON FUNCTION public.bandstand_valid_erp(jsonb) FROM PUBLIC,anon,authenticated;

CREATE OR REPLACE FUNCTION public.bandstand_upload_erp(recording_id uuid, recording jsonb)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM public.bandstand_consent WHERE user_id=auth.uid() AND erp_sharing AND policy_version='erp-sharing-v1') THEN RAISE EXCEPTION 'ERP sharing consent required'; END IF;
 IF NOT public.bandstand_valid_erp(recording) THEN RAISE EXCEPTION 'Invalid ERP payload'; END IF;
 -- Provisional quotas, to be revisited with measured use. Re-sending an already stored recording is free.
 IF NOT EXISTS(SELECT 1 FROM public.bandstand_erp_recordings e WHERE e.user_id=auth.uid() AND e.recording_id=bandstand_upload_erp.recording_id) THEN
  IF (SELECT count(*) FROM public.bandstand_erp_recordings e WHERE e.user_id=auth.uid() AND e.created_at>now()-interval '1 day')>=100 THEN RAISE EXCEPTION 'ERP sharing daily limit reached'; END IF;
  IF (SELECT count(*) FROM public.bandstand_erp_recordings e WHERE e.user_id=auth.uid())>=2000 THEN RAISE EXCEPTION 'ERP sharing storage limit reached'; END IF;
 END IF;
 INSERT INTO public.bandstand_erp_recordings(user_id,recording_id,payload) VALUES(auth.uid(),bandstand_upload_erp.recording_id,recording)
 ON CONFLICT ON CONSTRAINT bandstand_erp_recordings_pkey DO NOTHING;
END; $$;
REVOKE ALL ON FUNCTION public.bandstand_upload_erp(uuid,jsonb) FROM PUBLIC,anon;
GRANT EXECUTE ON FUNCTION public.bandstand_upload_erp(uuid,jsonb) TO authenticated;
COMMIT;
