from app.core.settings import settings
from supabase import Client, create_client


def get_supabase_client() -> Client:
    if not settings.supabase_url or not settings.supabase_secret_key:
        raise RuntimeError("Supabase server credentials are not configured")
    return create_client(settings.supabase_url, settings.supabase_secret_key)
