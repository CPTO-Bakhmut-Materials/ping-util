"""Підсумкова статистика ping."""

import math
from dataclasses import dataclass


@dataclass
class Statistics:
    """Накопичує дані про запити й відповіді та формує підсумок.

    Окремі значення RTT не зберігаються: для min/avg/max/mdev достатньо
    кількох сум, тому пам'ять не росте, навіть якщо ping працює годинами.
    """

    transmitted: int = 0
    received: int = 0
    errors: int = 0
    rtt_min: float = math.inf
    rtt_max: float = 0.0
    rtt_sum: float = 0.0
    rtt_sum_squares: float = 0.0

    def add_sent(self) -> None:
        self.transmitted += 1

    def add_error(self) -> None:
        self.errors += 1

    def add_reply(self, rtt_ms: float) -> None:
        self.received += 1
        self.rtt_min = min(self.rtt_min, rtt_ms)
        self.rtt_max = max(self.rtt_max, rtt_ms)
        self.rtt_sum += rtt_ms
        self.rtt_sum_squares += rtt_ms * rtt_ms

    def loss_percent(self) -> float:
        if self.transmitted == 0:
            return 0.0
        return (self.transmitted - self.received) * 100 / self.transmitted

    def rtt_avg(self) -> float:
        return self.rtt_sum / self.received

    def rtt_mdev(self) -> float:
        """Середнє відхилення RTT: sqrt(avg(rtt^2) - avg(rtt)^2), як в iputils."""
        avg = self.rtt_avg()
        variance = self.rtt_sum_squares / self.received - avg * avg
        # Через похибки округлення float дисперсія може вийти трохи меншою за 0.
        return math.sqrt(max(0.0, variance))

    def summary(self, host: str, elapsed_ms: float) -> list[str]:
        """Повертає рядки підсумку в форматі системного ping."""
        errors = f"+{self.errors} errors, " if self.errors else ""
        lines = [
            f"--- {host} ping statistics ---",
            f"{self.transmitted} packets transmitted, {self.received} received, {errors}"
            f"{self.loss_percent():g}% packet loss, time {elapsed_ms:.0f}ms",
        ]
        if self.received > 0:
            lines.append(
                f"rtt min/avg/max/mdev = {self.rtt_min:.3f}/{self.rtt_avg():.3f}/"
                f"{self.rtt_max:.3f}/{self.rtt_mdev():.3f} ms"
            )
        return lines
