import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.pipeline import run_triage
from app.core.settings import settings
from app.schemas.evidence import Evidence

print("supabase_url_configured=", bool(settings.supabase_url))
print("supabase_secret_configured=", bool(settings.supabase_secret_key))

result = run_triage(
    [
        Evidence(
            source="synthetic",
            event_type="supabase_smoke",
            severity_hint="high",
            message="synthetic persistence smoke",
        )
    ]
)
print("storage_status=", result["storage_status"])
print("request_id=", result["request_id"])
print("run_uuid=", result["run_uuid"])
