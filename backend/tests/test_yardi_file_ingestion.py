"""Focused Phase 4.15 Yardi staging safety regressions."""
from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest

from app.services.appfolio_file_ingestion import AppFolioFileIngestionError
from app.services.yardi_file_ingestion import stage_yardi_file


def _call(**overrides):
    args = dict(
        db=MagicMock(), run=SimpleNamespace(provider="YARDI", id=1, organization_id=1, source_account_ref="yardi-a"),
        filename="properties.csv", content=b"Property ID,Name\nP1,A\n",
        resource_override="PROPERTIES", sheet_name=None,
        explicit_mapping={"source_id": "Property ID", "name": "Name"},
        platform_user_id=1,
    )
    args.update(overrides)
    return stage_yardi_file(**args)


def test_reject_wrong_provider():
    with pytest.raises(AppFolioFileIngestionError, match="not a Yardi"):
        _call(run=SimpleNamespace(provider="APPFOLIO"))


def test_reject_unverified_resource():
    with pytest.raises(AppFolioFileIngestionError, match="PROPERTIES"):
        _call(resource_override="GENERAL_LEDGER")


def test_reject_unknown_source_header():
    with pytest.raises(AppFolioFileIngestionError, match="unknown source header"):
        _call(explicit_mapping={"source_id": "Imaginary"})


def test_reject_secret_column():
    with pytest.raises(AppFolioFileIngestionError):
        _call(content=b"Property ID,password\nP1,secret\n")
