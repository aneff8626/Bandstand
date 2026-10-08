-- Authenticated callers can delete only their own account. No research storage is enabled.
BEGIN;
CREATE OR REPLACE FUNCTION public.bandstand_delete_own_account()
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
DECLARE caller uuid := auth.uid();
BEGIN
 IF caller IS NULL THEN RAISE EXCEPTION 'Sign in required'; END IF;
 DELETE FROM auth.users WHERE id = caller;
END;
$$;
REVOKE ALL ON FUNCTION public.bandstand_delete_own_account() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.bandstand_delete_own_account() TO authenticated;
COMMIT;
