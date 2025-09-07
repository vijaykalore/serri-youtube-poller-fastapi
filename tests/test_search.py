import pytest

from app.youtube_client import APIKeyRotator


def test_api_key_rotation_basic():
    r = APIKeyRotator(["A", "B", "C"])
    assert r.pop_available() in {"A", "B", "C"}
    r.mark_exhausted()  # mark current as exhausted
    # next available should be one of others (eventually after rotate)
    assert r.pop_available() in {"A", "B", "C"}
