import pytest

from lgtv_remote.network import build_magic_packet, mac_to_bytes, normalize_mac


class TestNormalizeMac:
    def test_colon_separated(self):
        assert normalize_mac("F8:01:B4:A5:D8:B2") == "f8:01:b4:a5:d8:b2"

    def test_dash_separated(self):
        assert normalize_mac("f8-01-b4-a5-d8-b2") == "f8:01:b4:a5:d8:b2"

    def test_no_separator(self):
        assert normalize_mac("f801b4a5d8b2") == "f8:01:b4:a5:d8:b2"

    def test_mixed_case(self):
        assert normalize_mac("F8:01:b4:A5:d8:B2") == "f8:01:b4:a5:d8:b2"

    def test_too_short(self):
        with pytest.raises(ValueError):
            normalize_mac("F8:01:B4")

    def test_too_long(self):
        with pytest.raises(ValueError):
            normalize_mac("F8:01:B4:A5:D8:B2:00")

    def test_invalid_chars(self):
        with pytest.raises(ValueError):
            normalize_mac("ZZ:01:B4:A5:D8:B2")


class TestMacToBytes:
    def test_conversion(self):
        result = mac_to_bytes("F8:01:B4:A5:D8:B2")
        assert result == b"\xf8\x01\xb4\xa5\xd8\xb2"


class TestBuildMagicPacket:
    def test_length(self):
        packet = build_magic_packet("F8:01:B4:A5:D8:B2")
        assert len(packet) == 102

    def test_header(self):
        packet = build_magic_packet("F8:01:B4:A5:D8:B2")
        assert packet[:6] == b"\xff" * 6

    def test_mac_repeated(self):
        mac = "F8:01:B4:A5:D8:B2"
        packet = build_magic_packet(mac)
        mac_bytes = mac_to_bytes(mac)
        for i in range(16):
            offset = 6 + i * 6
            assert packet[offset : offset + 6] == mac_bytes
