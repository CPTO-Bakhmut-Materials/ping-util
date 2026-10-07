import unittest

from pyping.packet import (
    IcmpHeader,
    IPv4Header,
    build_echo_request,
    build_payload,
    checksum,
    parse_icmp_header,
    parse_ipv4_header,
    parse_packet,
)

from .helpers import make_echo_reply, make_ip_packet


class ChecksumTest(unittest.TestCase):
    def test_rfc1071_example(self) -> None:
        data = bytes.fromhex("0001f203f4f5f6f7")
        self.assertEqual(checksum(data), 0x220D)

    def test_odd_length_is_padded_with_zero(self) -> None:
        self.assertEqual(checksum(b"\x01"), checksum(b"\x01\x00"))

    def test_empty_data(self) -> None:
        self.assertEqual(checksum(b""), 0xFFFF)


class EchoRequestTest(unittest.TestCase):
    def test_known_packet(self) -> None:
        packet = build_echo_request(identifier=1, sequence=1, payload=b"")
        self.assertEqual(packet, bytes.fromhex("0800f7fd00010001"))

    def test_checksum_of_valid_packet_is_zero(self) -> None:
        packet = build_echo_request(identifier=4321, sequence=42, payload=build_payload(56))
        self.assertEqual(checksum(packet), 0)

    def test_header_fields(self) -> None:
        packet = build_echo_request(identifier=0xBEEF, sequence=3, payload=b"abc")
        self.assertEqual(
            parse_icmp_header(packet),
            IcmpHeader(type=8, code=0, identifier=0xBEEF, sequence=3),
        )


class ParseTest(unittest.TestCase):
    def test_ipv4_header(self) -> None:
        data = make_ip_packet(b"", ttl=58, source="8.8.8.8")
        self.assertEqual(
            parse_ipv4_header(data),
            IPv4Header(header_length=20, ttl=58, protocol=1, source="8.8.8.8", destination="10.0.0.1"),
        )

    def test_ipv4_header_with_options(self) -> None:
        data = make_ip_packet(b"", ihl=6)
        self.assertEqual(parse_ipv4_header(data).header_length, 24)

    def test_echo_reply(self) -> None:
        packet = parse_packet(make_echo_reply(identifier=7, sequence=2, payload=bytes(56)))
        assert packet is not None
        self.assertEqual(packet.icmp, IcmpHeader(type=0, code=0, identifier=7, sequence=2))
        self.assertEqual(packet.size, 64)

    def test_truncated_packet_is_rejected(self) -> None:
        self.assertIsNone(parse_packet(b"\x45\x00"))
        self.assertIsNone(parse_packet(make_ip_packet(b"\x00\x00\x00")))

    def test_corrupted_packet_is_rejected(self) -> None:
        data = bytearray(make_echo_reply(identifier=7, sequence=2, payload=b"hello"))
        data[-1] ^= 0xFF  # пошкоджуємо останній байт даних
        self.assertIsNone(parse_packet(bytes(data)))


if __name__ == "__main__":
    unittest.main()
