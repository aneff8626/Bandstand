-- Serialize per-user quota checks; preserve existing data and RPC interface.
BEGIN;
CREATE OR REPLACE FUNCTION public.bandstand_upload_erp(recording_id uuid, recording jsonb)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
BEGIN
 -- Serialize uploads for this account with consent changes. Counting before inserting
 -- without this lock lets simultaneous requests exceed the quota.
 PERFORM 1 FROM public.bandstand_consent WHERE user_id=auth.uid() AND erp_sharing AND policy_version='erp-sharing-v1' FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'ERP sharing consent required'; END IF;
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
