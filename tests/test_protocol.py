import pytest

from client.protocol import ProtocolError, format_status, parse_status


def test_status_round_trip():
    assert parse_status(" CH0=0, ch2 = 90 ") == {0: 0, 2: 90}
    assert format_status({2: 90, 0: 0}) == "CH0=0, CH2=90"


@pytest.mark.parametrize(
    ("response", "message"),
    [
        ("", "Empty"),
        (None, "Empty"),
        ("CH0=0,", "Malformed"),
        ("CH0", "Malformed"),
        ("X0=0", "channel name"),
        ("CHX=0", "Invalid STATUS"),
        ("CH0=x", "Invalid STATUS"),
        ("CH-1=0", "out of range"),
        ("CH0=181", "out of range"),
        ("CH0=0,CH0=1", "Duplicate"),
    ],
)
def test_rejects_malformed_status(response, message):
    with pytest.raises(ProtocolError, match=message):
        parse_status(response)
