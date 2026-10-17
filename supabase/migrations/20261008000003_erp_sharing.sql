BEGIN;
CREATE TABLE IF NOT EXISTS public.bandstand_erp_recordings(
 user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
 recording_id uuid NOT NULL,
 payload jsonb NOT NULL CHECK (pg_column_size(payload)<12000000),
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(user_id,recording_id)
);
ALTER TABLE public.bandstand_erp_recordings ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.bandstand_erp_recordings FROM PUBLIC,anon,authenticated;
CREATE OR REPLACE FUNCTION public.bandstand_set_erp_consent(allow_sharing boolean)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
BEGIN
 IF auth.uid() IS NULL THEN RAISE EXCEPTION 'Sign in required'; END IF;
 INSERT INTO public.bandstand_consent(user_id,policy_version,erp_sharing)
 VALUES(auth.uid(),'erp-sharing-v1',allow_sharing)
 ON CONFLICT(user_id) DO UPDATE SET policy_version='erp-sharing-v1',erp_sharing=excluded.erp_sharing,updated_at=now();
END; $$;
CREATE OR REPLACE FUNCTION public.bandstand_valid_erp(recording jsonb)
RETURNS boolean LANGUAGE plpgsql IMMUTABLE SET search_path='' AS $$
DECLARE t jsonb; ch record; n jsonb;
BEGIN
 IF recording IS NULL OR jsonb_typeof(recording) IS DISTINCT FROM 'object' OR recording->>'schema' IS DISTINCT FROM 'bandstand-erp-v1'
 OR COALESCE(recording->>'protocol','') NOT IN ('oddball','auditory','flanker','reward')
 OR jsonb_typeof(recording->'trials') IS DISTINCT FROM 'array'
 OR (recording - ARRAY['schema','protocol','trials']) <> '{}'::jsonb THEN RETURN false; END IF;
 IF jsonb_array_length(recording->'trials') NOT BETWEEN 1 AND 10000 OR octet_length(recording::text)>10000000 THEN RETURN false; END IF;
 FOR t IN SELECT value FROM jsonb_array_elements(recording->'trials') LOOP
  IF jsonb_typeof(t) IS DISTINCT FROM 'object' OR (t - ARRAY['condition','times','channels'])<>'{}'::jsonb OR COALESCE(t->>'condition','') NOT IN ('0','1') OR jsonb_typeof(t->'condition') IS DISTINCT FROM 'number'
   OR jsonb_typeof(t->'times') IS DISTINCT FROM 'array' OR jsonb_typeof(t->'channels') IS DISTINCT FROM 'object' THEN RETURN false; END IF;
  IF jsonb_array_length(t->'times') NOT BETWEEN 1 AND 1024 THEN RETURN false; END IF;
  FOR n IN SELECT value FROM jsonb_array_elements(t->'times') LOOP
   IF jsonb_typeof(n) IS DISTINCT FROM 'number' OR (n::text)::numeric NOT BETWEEN -10 AND 10 THEN RETURN false; END IF;
  END LOOP;
  FOR ch IN SELECT * FROM jsonb_each(t->'channels') LOOP
   IF ch.key NOT IN ('TP9','AF7','AF8','TP10') OR jsonb_typeof(ch.value) IS DISTINCT FROM 'object' OR (ch.value - ARRAY['accepted','wave'])<>'{}'::jsonb OR jsonb_typeof(ch.value->'accepted') IS DISTINCT FROM 'boolean' THEN RETURN false; END IF;
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
 INSERT INTO public.bandstand_erp_recordings(user_id,recording_id,payload) VALUES(auth.uid(),recording_id,recording)
 ON CONFLICT ON CONSTRAINT bandstand_erp_recordings_pkey DO NOTHING;
END; $$;
CREATE OR REPLACE FUNCTION public.bandstand_delete_erp()
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
BEGIN
 IF auth.uid() IS NULL THEN RAISE EXCEPTION 'Sign in required'; END IF;
 DELETE FROM public.bandstand_erp_recordings WHERE user_id=auth.uid();
END; $$;
REVOKE ALL ON FUNCTION public.bandstand_set_erp_consent(boolean),public.bandstand_upload_erp(uuid,jsonb),public.bandstand_delete_erp() FROM PUBLIC,anon;
GRANT EXECUTE ON FUNCTION public.bandstand_set_erp_consent(boolean),public.bandstand_upload_erp(uuid,jsonb),public.bandstand_delete_erp() TO authenticated;
CREATE OR REPLACE FUNCTION public.bandstand_sharing_status()
RETURNS jsonb LANGUAGE sql SECURITY DEFINER SET search_path='' AS $$
 SELECT jsonb_build_object('erp_sharing',COALESCE((SELECT erp_sharing FROM public.bandstand_consent WHERE user_id=auth.uid() AND policy_version='erp-sharing-v1'),false),'policy_version','erp-sharing-v1');
$$;
CREATE OR REPLACE FUNCTION public.bandstand_list_erp()
RETURNS TABLE(recording_id uuid,protocol text,created_at timestamptz,trial_count integer)
LANGUAGE sql SECURITY DEFINER SET search_path='' AS $$
 SELECT recording_id,payload->>'protocol',created_at,jsonb_array_length(payload->'trials') FROM public.bandstand_erp_recordings WHERE user_id=auth.uid() ORDER BY created_at DESC;
$$;
REVOKE ALL ON FUNCTION public.bandstand_sharing_status(),public.bandstand_list_erp() FROM PUBLIC,anon;
GRANT EXECUTE ON FUNCTION public.bandstand_sharing_status(),public.bandstand_list_erp() TO authenticated;
COMMIT;
