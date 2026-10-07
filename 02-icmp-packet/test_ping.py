"""Тести для уроку 2. Запуск: python3 -m unittest -v"""

import struct
import unittest

from ping import ICMP_HEADER_FORMAT, build_echo_request, build_payload, checksum


class ChecksumTest(unittest.TestCase):
    def test_rfc1071_example(self) -> None:
        # Приклад з RFC 1071, розділ 3: сума слів дорівнює 0xddf2,
        # отже контрольна сума є її інверсією, 0x220d.
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
        # Слова 0x0800 + 0x0000 + 0x0001 + 0x0001 = 0x0802, інверсія дорівнює 0xf7fd.
        packet = build_echo_request(identifier=1, sequence=1, payload=b"")
        self.assertEqual(packet, bytes.fromhex("0800f7fd00010001"))

    def test_checksum_of_valid_packet_is_zero(self) -> None:
        # Отримувач перевіряє пакет саме так: сума всього пакета разом
        # з полем checksum дає 0 (RFC 1071, розділ 1).
        packet = build_echo_request(identifier=4321, sequence=42, payload=build_payload(56))
        self.assertEqual(checksum(packet), 0)

    def test_packet_length(self) -> None:
        packet = build_echo_request(identifier=1, sequence=1, payload=build_payload(56))
        self.assertEqual(len(packet), 64)


if __name__ == "__main__":
    unittest.main()
