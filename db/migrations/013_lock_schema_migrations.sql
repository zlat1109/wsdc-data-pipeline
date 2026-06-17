-- Close public exposure of migration metadata (Security Advisor: rls_disabled_in_public).
ALTER TABLE public.schema_migrations ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.schema_migrations FROM anon, authenticated;
