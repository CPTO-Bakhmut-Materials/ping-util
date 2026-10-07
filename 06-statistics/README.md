# Урок 6. Статистика

[← Урок 5](../05-loop/README.md) · [До змісту](../README.md) · [Урок 7 →](../07-refactoring/README.md)

## Мета уроку

- Надрукувати повний підсумок, як системний ping: відсоток втрат, загальний час, min/avg/max/mdev.
- Винести підрахунок в окремий клас `Statistics` і протестувати його.
- Рахувати статистику, не зберігаючи всі значення RTT.

```console
$ ../netlab.sh 'python3 ping.py -c 3 10.0.0.2'
PING 10.0.0.2 (10.0.0.2) 56(84) bytes of data.
64 bytes from 10.0.0.2: icmp_seq=1 ttl=64 time=0.096 ms
64 bytes from 10.0.0.2: icmp_seq=2 ttl=64 time=0.185 ms
64 bytes from 10.0.0.2: icmp_seq=3 ttl=64 time=0.167 ms

--- 10.0.0.2 ping statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 2001ms
rtt min/avg/max/mdev = 0.096/0.149/0.185/0.039 ms
```

## Що змінилося порівняно з уроком 5

| Було | Стало |
|---|---|
| змінні `transmitted`, `received` у `main()` | клас `Statistics` |
| `N packets transmitted, M received` | повний підсумок у форматі iputils |
| — | `import math` |
| — | тести `StatisticsTest` |

---

## Теорія

### Що означає кожна величина

Формат підсумку описано в [уроці 1](../01-cli-skeleton/README.md#підсумкова-статистика). Формули такі:

| Величина | Формула | Джерело |
|---|---|---|
| packet loss | `(transmitted − received) / transmitted × 100` | [RFC 6673](https://www.rfc-editor.org/rfc/rfc6673) (метрика Round-trip Packet Loss), функція `finish()` в [`ping_common.c`](https://github.com/iputils/iputils/blob/master/ping/ping_common.c) |
| time | час від першого запиту до завершення, мс | `finish()` в iputils |
| min / max | найменший / найбільший RTT | — |
| avg | `Σrtt / n` — середнє арифметичне | — |
| mdev | `sqrt(Σrtt²/n − avg²)` | `finish()` в iputils |

### Що таке mdev

**mdev** показує, наскільки «стрибає» затримка. Попри назву («mean deviation»), iputils
рахує **стандартне відхилення** генеральної сукупності
([standard deviation](https://en.wikipedia.org/wiki/Standard_deviation)):

```
σ = sqrt( (1/n) · Σ (rtt_i − avg)² )
```

Цю формулу можна переписати так, щоб не зберігати окремі значення
([обчислювальна формула дисперсії](https://en.wikipedia.org/wiki/Variance#Definition)):

```
σ² = (1/n)·Σ rtt_i²  −  avg²
```

Тобто достатньо накопичувати лише **суму** і **суму квадратів**:

| Зберігаємо | Оновлення після кожної відповіді |
|---|---|
| `received` | `+= 1` |
| `rtt_min` | `min(rtt_min, rtt)` |
| `rtt_max` | `max(rtt_max, rtt)` |
| `rtt_sum` | `+= rtt` |
| `rtt_sum_squares` | `+= rtt * rtt` |

Пам'ять стала, O(1), навіть якщо ping працює добу. Системний ping робить так само:
поля `tsum` і `tsum2` в iputils.

> **Підводний камінь.** Різниця двох близьких великих чисел (`Σrtt²/n` і `avg²`)
> у [числах з плаваючою комою](https://docs.python.org/3/tutorial/floatingpoint.html)
> може дати крихітне **від'ємне** число замість 0. Тоді `math.sqrt` кине `ValueError`.
> Тому беремо `max(0.0, variance)`. Точніший спосіб описано в розділі
> [Welford's online algorithm](https://en.wikipedia.org/wiki/Algorithms_for_calculating_variance#Welford's_online_algorithm) (див. вправи).

### Класи

Стан статистики (лічильники й суми) та дії над ним (додати запит, додати відповідь,
сформувати підсумок) природно об'єднати в **клас**
([Python Tutorial: Classes](https://docs.python.org/3/tutorial/classes.html)):

- `__init__` — [конструктор](https://docs.python.org/3/reference/datamodel.html#object.__init__), який задає початковий стан;
- `self` — посилання на конкретний об'єкт, через нього методи читають і змінюють стан;
- методи — функції всередині класу.

Головне: клас **не залежить від мережі**. Його можна створити в тесті, «згодувати»
йому числа й перевірити результат. З `main()` так не вийде.

---

## Практика

### Крок 1. Клас Statistics

```python
class Statistics:
    def __init__(self) -> None:
        self.transmitted = 0
        self.received = 0
        self.rtt_min = math.inf
        self.rtt_max = 0.0
        self.rtt_sum = 0.0
        self.rtt_sum_squares = 0.0

    def add_sent(self) -> None:
        self.transmitted += 1

    def add_reply(self, rtt_ms: float) -> None:
        self.received += 1
        self.rtt_min = min(self.rtt_min, rtt_ms)
        self.rtt_max = max(self.rtt_max, rtt_ms)
        self.rtt_sum += rtt_ms
        self.rtt_sum_squares += rtt_ms * rtt_ms
```

[`math.inf`](https://docs.python.org/3/library/math.html#math.inf) — нескінченність.
Будь-яке перше значення RTT буде меншим, тож `min()` спрацює без окремої перевірки
«чи це перша відповідь».

### Крок 2. Обчислення

```python
    def loss_percent(self) -> float:
        if self.transmitted == 0:
            return 0.0
        return (self.transmitted - self.received) * 100 / self.transmitted

    def rtt_avg(self) -> float:
        return self.rtt_sum / self.received

    def rtt_mdev(self) -> float:
        avg = self.rtt_avg()
        variance = self.rtt_sum_squares / self.received - avg * avg
        return math.sqrt(max(0.0, variance))
```

- Перевірка `transmitted == 0` захищає від [`ZeroDivisionError`](https://docs.python.org/3/library/exceptions.html#ZeroDivisionError), якщо Ctrl+C натиснули ще до першого запиту.
- `rtt_avg()` і `rtt_mdev()` викликаємо лише коли `received > 0` (див. `summary()`).
- [`math.sqrt`](https://docs.python.org/3/library/math.html#math.sqrt) — квадратний корінь.

### Крок 3. Підсумок

```python
    def summary(self, host: str, elapsed_ms: float) -> list[str]:
        lines = [
            f"--- {host} ping statistics ---",
            f"{self.transmitted} packets transmitted, {self.received} received, "
            f"{self.loss_percent():g}% packet loss, time {elapsed_ms:.0f}ms",
        ]
        if self.received > 0:
            lines.append(
                f"rtt min/avg/max/mdev = {self.rtt_min:.3f}/{self.rtt_avg():.3f}/"
                f"{self.rtt_max:.3f}/{self.rtt_mdev():.3f} ms"
            )
        return lines
```

- Метод **повертає** рядки, а не друкує їх. Так його легко перевірити в тесті через `assertEqual`.
- `:g` — «загальний» формат ([format spec](https://docs.python.org/3/library/string.html#format-specification-mini-language)): `0`, `25`, `33.3333`. iputils використовує той самий `%g` з C, тому виходить `0% packet loss`, а не `0.0%`.
- `:.3f` — три знаки після коми, як `rtt min/avg/max/mdev` в iputils.
- Рядок `rtt ...` друкується лише за наявності відповідей. Системний ping поводиться так само.

### Крок 4. Використання в `main()`

```python
    stats = Statistics()
    start_time = time.perf_counter()

    with sock:
        try:
            while args.count is None or stats.transmitted < args.count:
                ...
                stats.add_sent()
                ...
                    stats.add_reply(rtt_ms)
                ...
        except KeyboardInterrupt:
            pass

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    print()
    for line in stats.summary(args.host, elapsed_ms):
        print(line)
    return EXIT_OK if stats.received > 0 else EXIT_NO_REPLY
```

Змінні `transmitted` і `received` зникли з `main()`, тепер ними займається `stats`.

---

## Запуск

Наша програма і системний ping у тій самій тестовій мережі:

```console
$ ../netlab.sh 'python3 ping.py -c 3 10.0.0.2 | tail -3; ping -c 3 10.0.0.2 | tail -3'

--- 10.0.0.2 ping statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 2001ms
rtt min/avg/max/mdev = 0.096/0.149/0.185/0.039 ms

--- 10.0.0.2 ping statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 2036ms
rtt min/avg/max/mdev = 0.044/0.076/0.107/0.025 ms
```

Формат однаковий. Значення RTT у нас трохи більші: Python повільніший за C, і між
`perf_counter()` та фактичною відправкою минає більше часу.

**Ctrl+C посеред роботи:**

```console
$ ../netlab.sh 'timeout -s INT 3.5 python3 ping.py 10.0.0.2'
PING 10.0.0.2 (10.0.0.2) 56(84) bytes of data.
64 bytes from 10.0.0.2: icmp_seq=1 ttl=64 time=0.103 ms
64 bytes from 10.0.0.2: icmp_seq=2 ttl=64 time=0.171 ms
64 bytes from 10.0.0.2: icmp_seq=3 ttl=64 time=0.160 ms
64 bytes from 10.0.0.2: icmp_seq=4 ttl=64 time=0.117 ms

--- 10.0.0.2 ping statistics ---
4 packets transmitted, 4 received, 0% packet loss, time 3437ms
rtt min/avg/max/mdev = 0.103/0.138/0.171/0.029 ms
```

**Без відповідей** (рядка `rtt` немає):

```console
$ ../netlab.sh 'python3 ping.py -c 3 10.1.0.99 | tail -2'
--- 10.1.0.99 ping statistics ---
3 packets transmitted, 0 received, 100% packet loss, time 3004ms
```

## Тести

```python
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
        self.assertAlmostEqual(stats.rtt_avg(), 11.895)
        self.assertAlmostEqual(stats.rtt_mdev(), 0.340, places=3)

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
```

- [`assertAlmostEqual(a, b, places=7)`](https://docs.python.org/3/library/unittest.html#unittest.TestCase.assertAlmostEqual) порівнює числа з плаваючою комою з точністю до `places` знаків. Через похибки округлення `assertEqual` для float ненадійний: `0.1 + 0.2 != 0.3`.
- Тест `test_summary_with_replies` перевіряє рядки **точно такі**, як друкує системний ping у [прикладі з уроку 1](../01-cli-skeleton/README.md#запускаємо-системний-ping).
- Ім'я `_` у `for _ in range(sent)` означає «змінна циклу не потрібна».

```console
$ python3 -m unittest
Ran 22 tests in 0.003s
OK
$ ../.venv/bin/mypy --strict .
Success: no issues found in 2 source files
```

## Код стає тісним

Подивіться на розмір [`ping.py`](ping.py) від уроку до уроку:

| Урок | Рядків у `ping.py` | Рядків у `main()` |
|---|---|---|
| 1 | 57 | 11 |
| 3 | 171 | 41 |
| 6 | 337 | 64 |

В одному файлі тепер усе: формат пакетів, сокет, цикл, статистика й вивід. Додати
нову можливість (наприклад, обробку ICMP-помилок) означає змінити функції, розкидані
по всьому файлу, і найдовшу функцію — `main()`. А `receive_reply()` досі не має тестів,
бо вимагає справжнього сокета. У [наступному уроці](../07-refactoring/README.md) це
виправимо, не змінюючи поведінки програми.

## Повний код

- [`ping.py`](ping.py)
- [`test_ping.py`](test_ping.py)

## Використані функції та модулі

| Що | Документація |
|---|---|
| класи | <https://docs.python.org/3/tutorial/classes.html> |
| `__init__` | <https://docs.python.org/3/reference/datamodel.html#object.__init__> |
| `math.inf` | <https://docs.python.org/3/library/math.html#math.inf> |
| `math.sqrt` | <https://docs.python.org/3/library/math.html#math.sqrt> |
| `min`, `max` | <https://docs.python.org/3/library/functions.html#min>, <https://docs.python.org/3/library/functions.html#max> |
| формат `:g`, `:.3f`, `:.0f` | <https://docs.python.org/3/library/string.html#format-specification-mini-language> |
| `list.append` | <https://docs.python.org/3/tutorial/datastructures.html#more-on-lists> |
| `ZeroDivisionError` | <https://docs.python.org/3/library/exceptions.html#ZeroDivisionError> |
| `TestCase.assertAlmostEqual` | <https://docs.python.org/3/library/unittest.html#unittest.TestCase.assertAlmostEqual> |
| числа з плаваючою комою | <https://docs.python.org/3/tutorial/floatingpoint.html> |

## Вправи

1. Порахуйте вручну min/avg/max/mdev для RTT `10, 20, 30` мс. Перевірте через `Statistics`.
2. Замініть суми на [алгоритм Велфорда](https://en.wikipedia.org/wiki/Algorithms_for_calculating_variance#Welford's_online_algorithm). Знайдіть набір RTT, для якого результати двох підходів помітно відрізняються. (Підказка: дуже великі значення з дуже малим розкидом.)
3. Додайте до статистики **медіану** RTT. Чи можна її рахувати без зберігання всіх значень?
4. Системний ping на Ctrl+\\ (SIGQUIT) друкує проміжну статистику й працює далі ([`ping(8)`](https://man7.org/linux/man-pages/man8/ping.8.html)). Реалізуйте це за допомогою [`signal.signal`](https://docs.python.org/3/library/signal.html#signal.signal).

## Джерела

- [RFC 6673](https://www.rfc-editor.org/rfc/rfc6673) — Round-trip Packet Loss Metric
- [RFC 2681](https://www.rfc-editor.org/rfc/rfc2681) — Round-trip Delay Metric
- [iputils `ping_common.c`](https://github.com/iputils/iputils/blob/master/ping/ping_common.c) — функція `finish()`: формат підсумку, `tsum`, `tsum2`
- [Variance](https://en.wikipedia.org/wiki/Variance), [Standard deviation](https://en.wikipedia.org/wiki/Standard_deviation) — формули
