"""Тести для уроку 4. Запуск: python3 -m unittest -v"""

import socket
import struct
import unittest

from ping import (
    ICMP_HEADER_FORMAT,
    IP_HEADER_FORMAT,
    build_echo_request,
    build_payload,
    checksum,
    format_rtt,
    parse_icmp_header,
    parse_ip_header,
)


def make_ip_header(ttl: int, source: str, ihl: int = 5) -> bytes:
    """Збирає заголовок IPv4 для тестів (version=4, protocol=1, тобто ICMP)."""
    header = struct.pack(
        IP_HEADER_FORMAT,
        (4 << 4) | ihl, 0, 84, 0, 0, ttl, socket.IPPROTO_ICMP, 0,
        socket.inet_aton(source), socket.inet_aton("10.0.0.1"),
    )
    # Якщо IHL > 5, після 20 байтів ідуть опції. Для тесту достатньо нулів.
    return header + bytes((ihl - 5) * 4)


class ChecksumTest(unittest.TestCase):
    def test_rfc1071_example(self) -> None:
        data = bytes.fromhex("0001f203f4f5f6f7")
        self.assertEqual(checksum(data), 0x220D)

    def test_odd_length_is_padded_with_zero(self) -> None:
        self.assertEqual(checksum(b"\x01"), checksum(b"\x01\x00"))

    def test_empty_data(self) -> None:
        self.assertEqual(checksum(b""), 0xFFFF)


class EchoRequestTest(unittest.TestCase):
    def test_header_fields(self) -> None:
        packet = build_echo_request(identifier=0x1234, sequence=7, payload=b"")
        type_, code, csum, identifier, sequence = struct.unpack(ICMP_HEADER_FORMAT, packet)
        self.assertEqual((type_, code, identifier, sequence), (8, 0, 0x1234, 7))

    def test_known_checksum(self) -> None:
        packet = build_echo_request(identifier=1, sequence=1, payload=b"")
        self.assertEqual(packet, bytes.fromhex("0800f7fd00010001"))

    def test_checksum_of_valid_packet_is_zero(self) -> None:
        packet = build_echo_request(identifier=4321, sequence=42, payload=build_payload(56))
        self.assertEqual(checksum(packet), 0)

    def test_packet_length(self) -> None:
        packet = build_echo_request(identifier=1, sequence=1, payload=build_payload(56))
        self.assertEqual(len(packet), 64)


class ParseTest(unittest.TestCase):
    def test_ip_header(self) -> None:
        header = make_ip_header(ttl=58, source="8.8.8.8")
        self.assertEqual(parse_ip_header(header), (20, 58, "8.8.8.8"))

    def test_ip_header_with_options(self) -> None:
        # IHL = 6: заголовок має 24 байти, бо містить 4 байти опцій.
        header = make_ip_header(ttl=64, source="127.0.0.1", ihl=6)
        self.assertEqual(parse_ip_header(header)[0], 24)

    def test_icmp_header(self) -> None:
        packet = build_echo_request(identifier=0xBEEF, sequence=3, payload=b"abc")
        self.assertEqual(parse_icmp_header(packet), (8, 0, 0xBEEF, 3))


class FormatRttTest(unittest.TestCase):
    def test_three_significant_digits(self) -> None:
        self.assertEqual(format_rtt(0.04567), "0.046")
        self.assertEqual(format_rtt(1.2345), "1.23")
        self.assertEqual(format_rtt(12.345), "12.3")
        self.assertEqual(format_rtt(123.45), "123")


if __name__ == "__main__":
    unittest.main()
