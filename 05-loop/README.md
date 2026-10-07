# Урок 5. Цикл

[← Урок 4](../04-reliability/README.md) · [До змісту](../README.md) · [Урок 6 →](../06-statistics/README.md)

## Мета уроку

- Відправляти запити один за одним, як системний ping.
- Додати опції `-c count` і `-i interval` та перевірку їх значень.
- Коректно зупинятися за Ctrl+C: надрукувати підсумок і повернути правильний код завершення.

```console
$ ../netlab.sh 'python3 ping.py -c 3 10.0.0.2'
PING 10.0.0.2 (10.0.0.2) 56(84) bytes of data.
64 bytes from 10.0.0.2: icmp_seq=1 ttl=64 time=0.134 ms
64 bytes from 10.0.0.2: icmp_seq=2 ttl=64 time=0.218 ms
64 bytes from 10.0.0.2: icmp_seq=3 ttl=64 time=0.128 ms

--- 10.0.0.2 ping statistics ---
3 packets transmitted, 3 received
```

## Що змінилося порівняно з уроком 4

| Було | Стало |
|---|---|
| один запит | цикл запитів |
| лише аргумент `host` | опції `-c COUNT`, `-i INTERVAL` |
| — | функції `positive_int()`, `positive_float()` для перевірки аргументів |
| — | константи `DEFAULT_INTERVAL`, `SEQUENCE_MASK` |
| — | обробка Ctrl+C (`KeyboardInterrupt`) |
| — | короткий підсумок: `N packets transmitted, M received` |

Функції `send_echo_request()` і `receive_reply()` не змінилися: вони працюють з одним
запитом, і цикл просто викликає їх кілька разів.

---

## Теорія

### Sequence Number

Кожен запит отримує свій номер: 1, 2, 3, … Він потрібен, щоб:

- зіставити відповідь із запитом ([RFC 792](https://www.rfc-editor.org/rfc/rfc792), с. 14);
- помітити **втрачені** пакети: пропуск номера означає, що запит або відповідь загубилися;
- помітити **запізнілі** відповіді: відповідь на запит №1, яка прийшла, поки ми чекаємо на №2, буде відкинута, бо `sequence` не збігається (урок 4).

Поле має 16 біт, тому після 65535 номер повертається до 0: `(n) & 0xFFFF`. За
секундного інтервалу до цього дійде через ~18 годин роботи.

### Інтервал

За замовчуванням ping відправляє запит раз на секунду (`-i`, [`ping(8)`](https://man7.org/linux/man-pages/man8/ping.8.html)).
Паузу рахуємо **від моменту відправки** попереднього запиту. Тоді очікування відповіді
є частиною інтервалу, і запити йдуть рівно раз на секунду:

```
 0.0      0.012             1.0      1.011             2.0
  │ send ──▶ reply │ sleep 0.988 │ send ──▶ reply │ sleep ... │ send
  └──────────── interval = 1.0 ──┘
```

> **Спрощення.** Наш ping **синхронний**: він чекає на відповідь (до `DEFAULT_TIMEOUT`)
> і тільки тоді відправляє наступний запит. Системний ping асинхронний: він відправляє
> запити за розкладом і водночас приймає відповіді на будь-який з них. Тому за
> `-i 0.2` і повільної мережі наш ping відправлятиме запити рідше, а запізнілі відповіді
> не врахує. Для навчальних цілей простота важливіша.

### Ctrl+C і сигнали

Коли користувач натискає Ctrl+C, термінал надсилає процесу сигнал **SIGINT**
([`signal(7)`](https://man7.org/linux/man-pages/man7/signal.7.html)). Python за
замовчуванням перетворює SIGINT на виняток [`KeyboardInterrupt`](https://docs.python.org/3/library/exceptions.html#KeyboardInterrupt)
([модуль `signal`](https://docs.python.org/3/library/signal.html#execution-of-python-signal-handlers)).
Виняток виникає в тому місці, де програма була в цей момент: у `recvfrom`, `time.sleep`
чи будь-де ще.

Системний ping після Ctrl+C друкує підсумок і завершується з кодом 0 або 1 залежно
від того, чи були відповіді. Робимо так само: перехоплюємо `KeyboardInterrupt` навколо
всього циклу.

`KeyboardInterrupt` — підклас [`BaseException`](https://docs.python.org/3/library/exceptions.html#BaseException),
а не `Exception` ([ієрархія винятків](https://docs.python.org/3/library/exceptions.html#exception-hierarchy)).
Тому `except Exception:` його не перехопить, і це зроблено навмисно.

### Перевірка аргументів у argparse

Параметр `type=` в [`add_argument`](https://docs.python.org/3/library/argparse.html#type)
приймає **будь-яку функцію**, яка перетворює рядок на значення. Якщо функція кидає
`ValueError`, `TypeError` або [`argparse.ArgumentTypeError`](https://docs.python.org/3/library/argparse.html#argparse.ArgumentTypeError),
argparse друкує помилку і завершує програму з кодом 2, як і належить ([урок 1](../01-cli-skeleton/README.md#коди-завершення)).

---

## Практика

### Крок 1. Типи аргументів

```python
def positive_int(text: str) -> int:
    """Тип аргументу для argparse: ціле число, більше за 0."""
    value = int(text)
    if value <= 0:
        raise argparse.ArgumentTypeError(f"must be greater than 0: {text!r}")
    return value


def positive_float(text: str) -> float:
    """Тип аргументу для argparse: дійсне число, більше за 0."""
    value = float(text)
    if value <= 0:
        raise argparse.ArgumentTypeError(f"must be greater than 0: {text!r}")
    return value
```

- [`int(text)`](https://docs.python.org/3/library/functions.html#int) і [`float(text)`](https://docs.python.org/3/library/functions.html#float) кидають `ValueError` для `"abc"`. argparse перехопить його сам.
- `{text!r}` — підставити [`repr(text)`](https://docs.python.org/3/library/functions.html#repr), тобто рядок у лапках ([format string syntax](https://docs.python.org/3/library/string.html#format-string-syntax)).

### Крок 2. Нові опції

```python
    parser.add_argument(
        "-c", dest="count", type=positive_int, default=None,
        help="зупинитися після COUNT запитів (за замовчуванням — до Ctrl+C)",
    )
    parser.add_argument(
        "-i", dest="interval", type=positive_float, default=DEFAULT_INTERVAL,
        help=f"пауза між запитами в секундах (за замовчуванням {DEFAULT_INTERVAL})",
    )
```

| Параметр | Значення | Документація |
|---|---|---|
| `"-c"` | ім'я з `-` означає **необов'язкову** опцію | [name or flags](https://docs.python.org/3/library/argparse.html#name-or-flags) |
| `dest="count"` | ім'я атрибута в результаті: `args.count` | [dest](https://docs.python.org/3/library/argparse.html#dest) |
| `type=positive_int` | функція перетворення й перевірки | [type](https://docs.python.org/3/library/argparse.html#type) |
| `default=None` | значення, якщо опцію не вказано. `None` означає «без обмеження». | [default](https://docs.python.org/3/library/argparse.html#default) |

### Крок 3. Цикл

```python
    identifier = os.getpid() & 0xFFFF
    payload = build_payload(payload_size)
    transmitted = 0
    received = 0

    with sock:
        try:
            while args.count is None or transmitted < args.count:
                sequence = (transmitted + 1) & SEQUENCE_MASK
                try:
                    send_time = send_echo_request(sock, address, identifier, sequence, payload)
                except OSError as exc:
                    print(f"ping: sendto: {exc.strerror}", file=sys.stderr)
                    return EXIT_ERROR
                transmitted += 1

                reply = receive_reply(sock, identifier, sequence, DEFAULT_TIMEOUT)
                if reply is None:
                    print(f"no answer yet for icmp_seq={sequence}")
                else:
                    source, ttl, size, receive_time = reply
                    rtt_ms = (receive_time - send_time) * 1000
                    print(...)
                    received += 1

                if args.count is not None and transmitted >= args.count:
                    break
                elapsed = time.perf_counter() - send_time
                time.sleep(max(0.0, args.interval - elapsed))
        except KeyboardInterrupt:
            pass

    print()
    print(f"--- {args.host} ping statistics ---")
    print(f"{transmitted} packets transmitted, {received} received")
    return EXIT_OK if received > 0 else EXIT_NO_REPLY
```

- Умова `args.count is None or ...`: без `-c` цикл нескінченний.
- `break` після останнього запиту: чекати інтервал після нього немає сенсу. Тому `ping -c 3` працює ~2 с, а не 3.
- [`time.sleep(seconds)`](https://docs.python.org/3/library/time.html#time.sleep) призупиняє програму. [`max(0.0, ...)`](https://docs.python.org/3/library/functions.html#max) захищає від від'ємного значення, якщо очікування відповіді тривало довше за інтервал.
- `except KeyboardInterrupt: pass` — вийти з циклу без повідомлення. [`pass`](https://docs.python.org/3/reference/simple_stmts.html#the-pass-statement) означає «нічого не робити». Блок `with sock:` все одно закриє сокет.
- `print()` без аргументів друкує порожній рядок, як системний ping перед `--- ... ---`.
- [Умовний вираз](https://docs.python.org/3/reference/expressions.html#conditional-expressions) `A if умова else B` обирає код завершення.

---

## Запуск

```console
$ ../netlab.sh 'time python3 ping.py -c 3 10.0.0.2'
PING 10.0.0.2 (10.0.0.2) 56(84) bytes of data.
64 bytes from 10.0.0.2: icmp_seq=1 ttl=64 time=0.134 ms
64 bytes from 10.0.0.2: icmp_seq=2 ttl=64 time=0.218 ms
64 bytes from 10.0.0.2: icmp_seq=3 ttl=64 time=0.128 ms

--- 10.0.0.2 ping statistics ---
3 packets transmitted, 3 received

real    0m2.082s
```

**Ctrl+C.** Утиліта [`timeout`](https://man7.org/linux/man-pages/man1/timeout.1.html) надсилає SIGINT через 2.5 с, як ніби користувач натиснув Ctrl+C:

```console
$ ../netlab.sh 'timeout -s INT 2.5 python3 ping.py 10.0.0.2'
PING 10.0.0.2 (10.0.0.2) 56(84) bytes of data.
64 bytes from 10.0.0.2: icmp_seq=1 ttl=64 time=0.115 ms
64 bytes from 10.0.0.2: icmp_seq=2 ttl=64 time=0.168 ms
64 bytes from 10.0.0.2: icmp_seq=3 ttl=64 time=0.165 ms

--- 10.0.0.2 ping statistics ---
3 packets transmitted, 3 received
```

**Немає відповідей:**

```console
$ ../netlab.sh 'python3 ping.py -c 2 10.1.0.99; echo "exit code: $?"'
PING 10.1.0.99 (10.1.0.99) 56(84) bytes of data.
no answer yet for icmp_seq=1
no answer yet for icmp_seq=2

--- 10.1.0.99 ping statistics ---
2 packets transmitted, 0 received
exit code: 1
```

**Неправильні аргументи:**

```console
$ python3 ping.py -c 0 example.com
usage: ping [-h] [-c COUNT] [-i INTERVAL] host
ping: error: argument -c: must be greater than 0: '0'

$ python3 ping.py -i abc example.com
usage: ping [-h] [-c COUNT] [-i INTERVAL] host
ping: error: argument -i: invalid positive_float value: 'abc'
```

## Тести

Додано тести аргументів командного рядка ([`test_ping.py`](test_ping.py)):

```python
class ArgsTest(unittest.TestCase):
    def test_count_and_interval(self) -> None:
        args = parse_args(["-c", "3", "-i", "0.2", "example.com"])
        self.assertEqual((args.count, args.interval), (3, 0.2))

    def test_positive_int(self) -> None:
        self.assertEqual(positive_int("5"), 5)
        with self.assertRaises(argparse.ArgumentTypeError):
            positive_int("0")
        with self.assertRaises(ValueError):
            positive_int("abc")

    def test_invalid_count_exits_with_code_2(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as ctx:
            parse_args(["-c", "0", "example.com"])
        self.assertEqual(ctx.exception.code, 2)
```

- [`assertRaises`](https://docs.python.org/3/library/unittest.html#unittest.TestCase.assertRaises), використаний як context manager, перевіряє, що блок кидає виняток. Через `ctx.exception` можна подивитися на сам виняток.
- argparse при помилці викликає [`sys.exit(2)`](https://docs.python.org/3/library/sys.html#sys.exit), а той кидає [`SystemExit`](https://docs.python.org/3/library/exceptions.html#SystemExit). Тому вихід із програми можна перевірити в тесті.
- [`contextlib.redirect_stderr`](https://docs.python.org/3/library/contextlib.html#contextlib.redirect_stderr) перенаправляє повідомлення argparse в [`io.StringIO`](https://docs.python.org/3/library/io.html#io.StringIO), щоб вони не засмічували вивід тестів.
- Тут видно користь параметра `argv` у `parse_args()` з [уроку 1](../01-cli-skeleton/README.md#крок-1-аргументи-командного-рядка).

```console
$ python3 -m unittest
Ran 16 tests in 0.002s
OK
$ ../.venv/bin/mypy --strict .
Success: no issues found in 2 source files
```

## Повний код

- [`ping.py`](ping.py)
- [`test_ping.py`](test_ping.py)

## Використані функції та модулі

| Що | Документація |
|---|---|
| `add_argument`: `dest`, `type`, `default` | <https://docs.python.org/3/library/argparse.html#the-add-argument-method> |
| `argparse.ArgumentTypeError` | <https://docs.python.org/3/library/argparse.html#argparse.ArgumentTypeError> |
| `int`, `float` | <https://docs.python.org/3/library/functions.html#int>, <https://docs.python.org/3/library/functions.html#float> |
| `max` | <https://docs.python.org/3/library/functions.html#max> |
| `time.sleep` | <https://docs.python.org/3/library/time.html#time.sleep> |
| `KeyboardInterrupt` | <https://docs.python.org/3/library/exceptions.html#KeyboardInterrupt> |
| сигнали в Python | <https://docs.python.org/3/library/signal.html#execution-of-python-signal-handlers> |
| `break`, `pass` | <https://docs.python.org/3/reference/simple_stmts.html#the-break-statement>, <https://docs.python.org/3/reference/simple_stmts.html#the-pass-statement> |
| умовний вираз | <https://docs.python.org/3/reference/expressions.html#conditional-expressions> |
| `!r` у f-рядках | <https://docs.python.org/3/library/string.html#format-string-syntax> |
| `TestCase.assertRaises` | <https://docs.python.org/3/library/unittest.html#unittest.TestCase.assertRaises> |
| `SystemExit` | <https://docs.python.org/3/library/exceptions.html#SystemExit> |
| `contextlib.redirect_stderr` | <https://docs.python.org/3/library/contextlib.html#contextlib.redirect_stderr> |
| `io.StringIO` | <https://docs.python.org/3/library/io.html#io.StringIO> |

## Вправи

1. Запустіть `python3 ping.py -c 5 -i 0.2 10.0.0.2` у тестовій мережі з `time` перед командою. Скільки триває робота? Порахуйте наперед.
2. Що станеться, якщо натиснути Ctrl+C **двічі** дуже швидко? Спробуйте і поясніть.
3. Додайте опцію `-w deadline`: загальний час роботи в секундах, після якого ping зупиняється незалежно від `-c` ([`ping(8)`](https://man7.org/linux/man-pages/man8/ping.8.html)).
4. Системний ping з `-i` менше 0.2 вимагає root. Знайдіть у `ping(8)`, чому, і подумайте, чи потрібне таке обмеження нашій програмі.
5. Як змінити цикл, щоб запити відправлялися **за розкладом** (0.0, 1.0, 2.0 …), навіть якщо відповідь затримується? (Підказка: [`selectors`](https://docs.python.org/3/library/selectors.html) або окремий потік.)

## Джерела

- [RFC 792](https://www.rfc-editor.org/rfc/rfc792) — Sequence Number
- [`ping(8)`](https://man7.org/linux/man-pages/man8/ping.8.html) — опції `-c`, `-i`, `-w`
- [`signal(7)`](https://man7.org/linux/man-pages/man7/signal.7.html) — SIGINT
- [argparse tutorial](https://docs.python.org/3/howto/argparse.html)
