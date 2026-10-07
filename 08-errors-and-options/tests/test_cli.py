import argparse
import contextlib
import io
import unittest

from pyping.cli import (
    format_error,
    format_reply,
    format_rtt,
    int_in_range,
    parse_args,
    positive_float,
    positive_int,
)
from pyping.pinger import EchoReply, IcmpError


class ArgsTest(unittest.TestCase):
    def test_defaults(self) -> None:
        args = parse_args(["example.com"])
        self.assertEqual(
            (args.host, args.count, args.interval, args.size, args.ttl, args.timeout, args.verbose),
            ("example.com", None, 1.0, 56, None, 1.0, False),
        )

    def test_options(self) -> None:
        args = parse_args(
            ["-c", "3", "-i", "0.2", "-s", "1000", "-t", "5", "-W", "2", "-v", "example.com"]
        )
        self.assertEqual(
            (args.count, args.interval, args.size, args.ttl, args.timeout, args.verbose),
            (3, 0.2, 1000, 5, 2.0, True),
        )

    def test_int_in_range(self) -> None:
        ttl = int_in_range(1, 255)
        self.assertEqual(ttl("1"), 1)
        self.assertEqual(ttl("255"), 255)
        with self.assertRaises(argparse.ArgumentTypeError):
            ttl("0")
        with self.assertRaises(argparse.ArgumentTypeError):
            ttl("256")

    def test_positive_numbers(self) -> None:
        self.assertEqual(positive_int("5"), 5)
        self.assertEqual(positive_float("0.5"), 0.5)
        with self.assertRaises(argparse.ArgumentTypeError):
            positive_int("0")
        with self.assertRaises(argparse.ArgumentTypeError):
            positive_float("-1")

    def test_invalid_count_exits_with_code_2(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as ctx:
            parse_args(["-c", "0", "example.com"])
        self.assertEqual(ctx.exception.code, 2)


class OutputTest(unittest.TestCase):
    def test_format_rtt(self) -> None:
        self.assertEqual(format_rtt(0.04567), "0.046")
        self.assertEqual(format_rtt(1.2345), "1.23")
        self.assertEqual(format_rtt(12.345), "12.3")
        self.assertEqual(format_rtt(123.45), "123")

    def test_format_reply(self) -> None:
        reply = EchoReply(source="8.8.8.8", sequence=1, ttl=119, size=64, rtt_ms=12.04)
        self.assertEqual(
            format_reply(reply), "64 bytes from 8.8.8.8: icmp_seq=1 ttl=119 time=12.0 ms"
        )

    def test_format_error(self) -> None:
        error = IcmpError(source="10.0.0.2", sequence=1, message="Time to live exceeded")
        self.assertEqual(format_error(error), "From 10.0.0.2 icmp_seq=1 Time to live exceeded")


if __name__ == "__main__":
    unittest.main()
