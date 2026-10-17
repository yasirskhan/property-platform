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

    direct_run = operations[base + "/runs/{run_id}"]
    assert "get" in direct_run and "post" not in direct_run
    assert direct_run["get"].get("security"), "Older run lookup must require authentication"

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


def test_yardi_committed_identity_inventory_is_authenticated_and_read_only():
    operations = app.openapi()["paths"]
    path = "/api/platform/migrations/yardi/runs/{run_id}/bindings"
    assert path in operations
    assert "get" in operations[path]
    assert "post" not in operations[path]
    read = operations[path]["get"]
    assert read.get("security"), "Durable mappings must require authenticated platform staff"
    parameters = {param["name"]: param for param in read["parameters"]}
    assert {"run_id", "resource", "offset", "limit"} <= parameters.keys()


def test_yardi_per_lease_relationship_diagnostics_are_authenticated_get_only():
    operations = app.openapi()["paths"]
    path = "/api/platform/migrations/yardi/runs/{run_id}/lease-relationships"
    assert path in operations
    assert "get" in operations[path]
    assert "post" not in operations[path]
    method = operations[path]["get"]
    assert method.get("security"), "Relationship preview must require staff authentication"
    parameters = {parameter["name"] for parameter in method["parameters"]}
    assert {"run_id", "offset", "limit"} <= parameters


def test_yardi_cross_upload_source_collisions_are_authenticated_read_only():
    operations = app.openapi()["paths"]
    path = "/api/platform/migrations/yardi/runs/{run_id}/source-collisions"
    assert path in operations
    assert "get" in operations[path] and "post" not in operations[path]
    query = operations[path]["get"]
    assert query.get("security")
    assert {"run_id", "resource", "offset", "limit"} <= {
        p["name"] for p in query.get("parameters", [])
    }


def test_yardi_lease_identity_acceptance_is_authenticated_post_only():
    operations = app.openapi()["paths"]
    path = "/api/platform/migrations/yardi/runs/{run_id}/staged-rows/{row_id}/accept-lease-relationship"
    assert path in operations
    assert "post" in operations[path] and "get" not in operations[path]
    method = operations[path]["post"]
    assert method.get("security"), "Acceptance requires platform staff authorization"
    assert {"run_id", "row_id"} <= {param["name"] for param in method.get("parameters", [])}
