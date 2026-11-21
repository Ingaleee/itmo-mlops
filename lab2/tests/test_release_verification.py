import pytest

from scripts.verify_release import VerificationError, verify_request_id


def test_direct_service_preserves_client_correlation():
    verify_request_id("acceptance-001", "acceptance-001", "acceptance-001", "preserve")
    with pytest.raises(VerificationError, match="propagation"):
        verify_request_id("acceptance-001", "changed", "changed", "preserve")


def test_gateway_correlates_the_uuid_assigned_at_the_edge():
    effective = "193cbe68-b7f4-4b1a-9c0d-101b070a7377"
    verify_request_id("acceptance-001", effective, effective, "gateway")


@pytest.mark.parametrize("body,header", [
    ("193cbe68-b7f4-4b1a-9c0d-101b070a7377", "ec77cd55-5d6b-4e45-a41b-36127030fd0a"),
    (None, None), ("", ""), ("arbitrary", "arbitrary"),
])
def test_gateway_does_not_hide_lost_or_invalid_correlation(body, header):
    with pytest.raises(VerificationError):
        verify_request_id("acceptance-001", body, header, "gateway")
