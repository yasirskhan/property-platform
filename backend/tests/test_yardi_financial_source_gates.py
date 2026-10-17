"""Unsupported Yardi accounting imports must remain gated."""
import pytest

from app.services.appfolio_file_ingestion import AppFolioFileIngestionError
from test_yardi_file_ingestion import _call


@pytest.mark.parametrize("resource", [
    "GL_ACCOUNTS", "OPEN_RECEIVABLES", "LEASE_CHARGES",
    "OPEN_PAYABLES", "BANK_ACCOUNTS", "CURRENT_YEAR_BUDGETS",
    "OUTSTANDING_CHECKS", "TRIAL_BALANCE", "GENERAL_LEDGER",
])
def test_yardi_financial_import_requires_verified_source_contract(resource):
    with pytest.raises(AppFolioFileIngestionError, match="require verified source contracts"):
        _call(resource_override=resource)
