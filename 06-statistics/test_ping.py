"""Тести для уроку 6. Запуск: python3 -m unittest -v"""

import argparse
import contextlib
import io
import socket
import struct
import unittest

from ping import (
    ICMP_HEADER_FORMAT,
    IP_HEADER_FORMAT,
    Statistics,
    build_echo_request,
    build_payload,
    checksum,
    format_rtt,
    parse_args,
    parse_icmp_header,
    parse_ip_header,
    positive_float,
    positive_int,
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


class ArgsTest(unittest.TestCase):
    def test_defaults(self) -> None:
        args = parse_args(["example.com"])
        self.assertEqual((args.host, args.count, args.interval), ("example.com", None, 1.0))

    def test_count_and_interval(self) -> None:
        args = parse_args(["-c", "3", "-i", "0.2", "example.com"])
        self.assertEqual((args.count, args.interval), (3, 0.2))

    def test_positive_int(self) -> None:
        self.assertEqual(positive_int("5"), 5)
        with self.assertRaises(argparse.ArgumentTypeError):
            positive_int("0")
        with self.assertRaises(ValueError):
            positive_int("abc")

    def test_positive_float(self) -> None:
        self.assertEqual(positive_float("0.5"), 0.5)
        with self.assertRaises(argparse.ArgumentTypeError):
            positive_float("-1")

    def test_invalid_count_exits_with_code_2(self) -> None:
        # argparse друкує помилку в stderr і викликає sys.exit(2).
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as ctx:
            parse_args(["-c", "0", "example.com"])
        self.assertEqual(ctx.exception.code, 2)


class StatisticsTest(unittest.TestCase):
    def make_stats(self, sent: int, rtts: list[float]) -> Statistics:
        stats = Statistics()
        for _ in range(sent):
            stats.add_sent()
        for rtt in rtts:
            stats.add_reply(rtt)
        return stats

    def test_rtt_values(self) -> None:
        # Значення підібрано так, щоб підсумок збігся з прикладом з уроку 1:
        # rtt min/avg/max/mdev = 11.416/11.895/12.165/0.340 ms
        stats = self.make_stats(3, [12.165, 11.416, 12.104])
        self.assertAlmostEqual(stats.rtt_min, 11.416)
        self.assertAlmostEqual(stats.rtt_max, 12.165)
        self.assertAlmostEqual(stats.rtt_avg(), 11.895)
        self.assertAlmostEqual(stats.rtt_mdev(), 0.340, places=3)

    def test_mdev_of_equal_values_is_zero(self) -> None:
        stats = self.make_stats(3, [5.0, 5.0, 5.0])
        self.assertEqual(stats.rtt_mdev(), 0.0)

    def test_loss_percent(self) -> None:
        self.assertEqual(self.make_stats(4, [1.0, 1.0, 1.0]).loss_percent(), 25.0)
        self.assertEqual(self.make_stats(0, []).loss_percent(), 0.0)

    def test_summary_with_replies(self) -> None:
        stats = self.make_stats(3, [12.165, 11.416, 12.104])
        self.assertEqual(
            stats.summary("example.com", 2002.4),
            [
                "--- example.com ping statistics ---",
                "3 packets transmitted, 3 received, 0% packet loss, time 2002ms",
                "rtt min/avg/max/mdev = 11.416/11.895/12.165/0.340 ms",
            ],
        )

    def test_summary_without_replies(self) -> None:
        stats = self.make_stats(3, [])
        self.assertEqual(
            stats.summary("10.1.0.99", 2003.0),
            [
                "--- 10.1.0.99 ping statistics ---",
                "3 packets transmitted, 0 received, 100% packet loss, time 2003ms",
            ],
        )

    def test_loss_is_printed_like_iputils(self) -> None:
        # iputils друкує відсоток у форматі %g: 33.3333, а не 33.33333333333333.
        stats = self.make_stats(3, [1.0, 1.0])
        self.assertIn("33.3333% packet loss", stats.summary("h", 0)[1])


if __name__ == "__main__":
    unittest.main()
