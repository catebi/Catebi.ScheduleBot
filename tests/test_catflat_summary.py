"""Level 2: the today's-schedule summary lines of the cat-flat overview."""

from datetime import UTC, datetime

import pytest

from app.services import catflat_service as svc
from app.translations import catflat_schedule_cleaning_none, catflat_schedule_medical_none


class FakeSchedule:
    all_result = []

    @classmethod
    def all(cls, **kw):
        return cls.all_result


@pytest.fixture
def fake_schedule(monkeypatch):
    FakeSchedule.all_result = []
    monkeypatch.setattr(svc, "Schedule", FakeSchedule)
    return FakeSchedule


def _shift(shift_type, telegram="@alice"):
    return type("S", (), {"date": datetime(2024, 6, 8, 10, 0, tzinfo=UTC), "type": shift_type, "telegram": telegram})()


async def test_summary_empty_day(fake_schedule):
    lines = await svc._todays_schedule_summary()
    assert lines == [catflat_schedule_cleaning_none["ru"], catflat_schedule_medical_none["ru"]]


async def test_summary_counts_regular_cleaning(fake_schedule):
    fake_schedule.all_result = [_shift("cleaning")]
    lines = await svc._todays_schedule_summary()
    assert "@alice" in lines[0]


async def test_summary_counts_general_cleaning_as_cleaning(fake_schedule):
    fake_schedule.all_result = [_shift("general_cleaning")]
    lines = await svc._todays_schedule_summary()
    # A weekend general-cleaning shift shows up in the cleaning line, not "no cleaning".
    assert "@alice" in lines[0]
    assert lines[0] != catflat_schedule_cleaning_none["ru"]


async def test_summary_medical_goes_to_medical_line(fake_schedule):
    fake_schedule.all_result = [_shift("medical", "@bob")]
    lines = await svc._todays_schedule_summary()
    assert lines[0] == catflat_schedule_cleaning_none["ru"]
    assert "@bob" in lines[1]
