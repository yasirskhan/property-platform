"""Operational Yardi staff workflow contract used by the platform console.

No source file, customer Property, Unit, Tenant or accounting record is
created here. Protects the authenticated upload/review endpoints consumed by
the platform-admin Yardi migration page.
"""
from app.main import app


def test_yardi_staff_workflow_endpoints_are_mounted_and_upload_is_multipart():
    operations = app.openapi()["paths"]
    base = "/api/platform/migrations/yardi"
    required = {
        "/runs": {"get", "post"},
        "/resource-readiness": {"get"},
        "/runs/{run_id}/uploads": {"get", "post"},
        "/runs/{run_id}/uploads/{upload_id}/rows": {"get"},
        "/runs/{run_id}/reconciliation": {"get"},
        "/runs/{run_id}/review-dry-run": {"get", "post"},
    }
    for tail, methods in required.items():
        assert base + tail in operations, tail
        assert methods <= operations[base + tail].keys(), tail

    upload = operations[base + "/runs/{run_id}/uploads"]["post"]
    media = upload["requestBody"]["content"]
    assert "multipart/form-data" in media
    assert "application/json" not in media
    assert upload.get("security"), "Yardi source uploads require platform authentication"
    for endpoint in (
        "/runs",
        "/runs/{run_id}/uploads",
        "/runs/{run_id}/reconciliation",
        "/runs/{run_id}/review-dry-run",
    ):
        assert any(operation.get("security") for operation in operations[base + endpoint].values())

    readiness = operations[base + "/resource-readiness"]
    assert readiness["get"].get("security")
