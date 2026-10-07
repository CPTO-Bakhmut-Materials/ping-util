import unittest

from pyping.stats import Statistics


def make_stats(sent: int, rtts: list[float]) -> Statistics:
    stats = Statistics()
    for _ in range(sent):
        stats.add_sent()
    for rtt in rtts:
        stats.add_reply(rtt)
    return stats


class StatisticsTest(unittest.TestCase):
    def test_rtt_values(self) -> None:
        # Значення підібрано так, щоб підсумок збігся з прикладом з уроку 1:
        # rtt min/avg/max/mdev = 11.416/11.895/12.165/0.340 ms
        stats = make_stats(3, [12.165, 11.416, 12.104])
        self.assertAlmostEqual(stats.rtt_min, 11.416)
        self.assertAlmostEqual(stats.rtt_max, 12.165)
        self.assertAlmostEqual(stats.rtt_avg(), 11.895)
        self.assertAlmostEqual(stats.rtt_mdev(), 0.340, places=3)

    def test_mdev_of_equal_values_is_zero(self) -> None:
        self.assertEqual(make_stats(3, [5.0, 5.0, 5.0]).rtt_mdev(), 0.0)

    def test_loss_percent(self) -> None:
        self.assertEqual(make_stats(4, [1.0, 1.0, 1.0]).loss_percent(), 25.0)
        self.assertEqual(make_stats(0, []).loss_percent(), 0.0)

    def test_dataclass_equality(self) -> None:
        # @dataclass генерує __eq__, тому стани можна порівнювати цілком.
        self.assertEqual(make_stats(2, []), Statistics(transmitted=2))

    def test_summary_with_replies(self) -> None:
        stats = make_stats(3, [12.165, 11.416, 12.104])
        self.assertEqual(
            stats.summary("example.com", 2002.4),
            [
                "--- example.com ping statistics ---",
                "3 packets transmitted, 3 received, 0% packet loss, time 2002ms",
                "rtt min/avg/max/mdev = 11.416/11.895/12.165/0.340 ms",
            ],
        )

    def test_summary_without_replies(self) -> None:
        self.assertEqual(
            make_stats(3, []).summary("10.1.0.99", 2003.0),
            [
                "--- 10.1.0.99 ping statistics ---",
                "3 packets transmitted, 0 received, 100% packet loss, time 2003ms",
            ],
        )


if __name__ == "__main__":
    unittest.main()
