-- No recording payloads or embeddings. No client uploads until separately enabled.
BEGIN;
REVOKE EXECUTE ON FUNCTION public.rls_auto_enable() FROM PUBLIC, anon, authenticated;
CREATE TABLE IF NOT EXISTS public.bandstand_consent (
 user_id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
 policy_version text NOT NULL,
 erp_sharing boolean NOT NULL DEFAULT false,
 decoder_sharing boolean NOT NULL DEFAULT false CHECK (decoder_sharing = false),
 updated_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE public.bandstand_consent ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.bandstand_consent FROM PUBLIC, anon, authenticated;
CREATE TABLE IF NOT EXISTS public.bandstand_model_releases (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 version text UNIQUE NOT NULL,
 sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
 storage_path text NOT NULL,
 privacy_reviewed boolean NOT NULL DEFAULT false,
 created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE public.bandstand_model_releases ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.bandstand_model_releases FROM PUBLIC, anon, authenticated;
COMMENT ON TABLE public.bandstand_consent IS 'Enrollment foundation; client grants withheld until reviewed account and deletion flows exist.';
COMMENT ON TABLE public.bandstand_model_releases IS 'Only reviewed shared models; never personal decoder snapshots or phrase banks.';
COMMIT;
