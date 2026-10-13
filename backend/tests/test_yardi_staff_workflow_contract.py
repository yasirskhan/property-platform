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
    candidates = operations[base + "/runs/{run_id}/existing-targets"]["get"]
    assert candidates.get("security")
    parameter_names = {param["name"] for param in candidates.get("parameters", [])}
    assert {"resource", "q", "limit"} <= parameter_names


def test_yardi_staff_review_and_existing_identity_binding_operations_are_authenticated():
    operations = app.openapi()["paths"]
    base = "/api/platform/migrations/yardi/runs/{run_id}"
    review = {
        "/staged-rows/{row_id}/skip",
        "/staged-rows/{row_id}/match-property",
        "/staged-rows/{row_id}/match-unit",
        "/staged-rows/{row_id}/match-owner",
        "/staged-rows/{row_id}/match-vendor",
        "/staged-rows/{row_id}/match-tenant",
        "/properties/bind-reviewed-matches",
        "/bind-reviewed-units",
        "/bind-reviewed-owners",
        "/bind-reviewed-vendors",
        "/bind-reviewed-tenants",
    }
    for suffix in review:
        path = base + suffix
        assert path in operations, path
        method = operations[path]["post"]
        assert method.get("security"), path
        assert "application/json" in method["requestBody"]["content"], path
