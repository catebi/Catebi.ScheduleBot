"""Level 1: the cat-flat changes-message builder (pure function)."""

from app.jobs.catflat import _build_changes_message
from app.translations import changes_header, changes_new, changes_none


def _cat(request_id="123", status="принята в кд"):
    full = {
        "request_id": request_id,
        "record_id": "rec1",
        "request_record_id": "req1",
        "requestor_name": "Anna",
        "status": status,
        "notes_kk": "",
        "fields_data": {},
    }
    return {"request_id": request_id, "record_id": "rec1", "full_cat_data": full}


def test_no_changes_returns_none_message():
    assert _build_changes_message([], [], {}, []) == changes_none["ru"]


def test_new_cats_section():
    msg = _build_changes_message([_cat("123")], [], {}, [])
    assert msg.startswith(changes_header["ru"])
    assert changes_new["ru"] in msg
    assert "123" in msg


def test_status_change_section():
    cat = _cat("55", status="готова к выписке")
    msg = _build_changes_message([], [], {("принята в кд", "готова к выписке"): [cat]}, [])
    assert "принята в кд -> готова к выписке" in msg
    assert "55" in msg
