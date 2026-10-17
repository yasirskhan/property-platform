"""Serialize overlapping Yardi Property target reviews before collision checks."""
from unittest.mock import MagicMock

from app.routers.yardi_migrations import _locked_yardi_review_target


def test_yardi_property_review_acquires_row_lock_in_target_query():
    db = MagicMock()
    expected = (17,)
    db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = expected
    found = _locked_yardi_review_target(db, organization_id=9, property_id=17)
    assert found == expected
    db.query.return_value.filter.return_value.with_for_update.assert_called_once_with()
    db.query.return_value.filter.return_value.with_for_update.return_value.first.assert_called_once_with()
