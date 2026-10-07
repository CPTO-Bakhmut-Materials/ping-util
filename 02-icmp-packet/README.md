# Урок 2. Пакет ICMP Echo Request

[← Урок 1](../01-cli-skeleton/README.md) · [До змісту](../README.md) · [Урок 3 →](../03-first-ping/README.md)

## Мета уроку

- Розібратися у форматі повідомлення ICMP Echo ([RFC 792](https://www.rfc-editor.org/rfc/rfc792)).
- Навчитися перетворювати числа на байти в мережевому порядку за допомогою модуля `struct`.
- Реалізувати контрольну суму Internet Checksum ([RFC 1071](https://www.rfc-editor.org/rfc/rfc1071)).
- Написати перші автоматичні тести.

У цьому уроці пакет ще **не відправляється**. Ми збираємо його в пам'яті й
показуємо вміст. Відправка буде в уроці 3, а для неї потрібен правильно
зібраний пакет.

```console
$ python3 ping.py example.com
PING example.com (104.20.23.154) 56(84) bytes of data.
type=8 code=0 checksum=0x2833 id=55480 seq=1 payload=56 bytes
0000  08 00 28 33 d8 b8 00 01 00 01 02 03 04 05 06 07
0010  08 09 0a 0b 0c 0d 0e 0f 10 11 12 13 14 15 16 17
0020  18 19 1a 1b 1c 1d 1e 1f 20 21 22 23 24 25 26 27
0030  28 29 2a 2b 2c 2d 2e 2f 30 31 32 33 34 35 36 37
```

## Що змінилося порівняно з уроком 1

| Було | Стало |
|---|---|
| `PING host (ip)` | `PING host (ip) 56(84) bytes of data.`, як у системного ping |
| — | константи формату ICMP-заголовка |
| — | функції `checksum()`, `build_payload()`, `build_echo_request()` |
| — | функції для показу пакета: `describe_packet()`, `hexdump()` |
| — | файл тестів [`test_ping.py`](test_ping.py) |

Функції `parse_args()` і `resolve()` не змінилися. Усі нові функції мають анотації типів
(див. [урок 1, крок 4](../01-cli-skeleton/README.md#крок-4-анотації-типів-type-hints)).
Тип `bytes` у сигнатурах означає, що функція працює з **сирими байтами** пакета, а не з текстом (`str`).

---

## Теорія

### Формат повідомлення Echo / Echo Reply

[RFC 792](https://www.rfc-editor.org/rfc/rfc792) (сторінка 14, розділ «Echo or Echo Reply Message»)
визначає формат так. Кожен рядок схеми — 32 біти (4 байти), цифри зверху — номери бітів:

```
    0                   1                   2                   3
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |     Type      |     Code      |          Checksum             |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |           Identifier          |        Sequence Number        |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |     Data ...
   +-+-+-+-+-
```

| Поле | Розмір | Значення для Echo Request | Пояснення |
|---|---|---|---|
| **Type** | 1 байт | `8` | Тип повідомлення: 8 — Echo Request, 0 — Echo Reply. Повний перелік типів — у [реєстрі IANA](https://www.iana.org/assignments/icmp-parameters/icmp-parameters.xhtml#icmp-parameters-types). |
| **Code** | 1 байт | `0` | Уточнює тип. Для Echo завжди 0 ([IANA, коди для type 8](https://www.iana.org/assignments/icmp-parameters/icmp-parameters.xhtml#icmp-parameters-codes-8)). |
| **Checksum** | 2 байти | обчислюється | Контрольна сума всього ICMP-повідомлення, тобто заголовка разом з даними ([RFC 1071](https://www.rfc-editor.org/rfc/rfc1071)). Під час обчислення це поле дорівнює 0. |
| **Identifier** | 2 байти | наприклад, PID | За RFC 792 це поле «може використовуватися як порт у TCP чи UDP, щоб ідентифікувати сеанс». Дає змогу відрізнити відповіді на **наш** ping від відповідей іншим програмам. |
| **Sequence Number** | 2 байти | 1, 2, 3, … | Номер запиту в межах сеансу. Саме він виводиться як `icmp_seq`. |
| **Data** | довільний | 56 байтів | Довільні дані. Отримувач зобов'язаний повернути їх без змін ([RFC 1122, розд. 3.2.2.6](https://www.rfc-editor.org/rfc/rfc1122#section-3.2.2.6)). |

Отже, заголовок займає рівно **8 байтів**, і разом із 56 байтами даних маємо 64 байти.
Це ті самі `64 bytes`, які друкує системний ping (див. [урок 1](../01-cli-skeleton/README.md#рядок-відповіді)).

### Мережевий порядок байтів

Число `0x1234` займає два байти, і їх можна записати в пам'ять у двох порядках:

| Порядок | Байти | Де використовується |
|---|---|---|
| **big-endian**, старший байт першим | `12 34` | у мережевих протоколах («network byte order») |
| **little-endian**, молодший байт першим | `34 12` | у процесорах x86 і більшості ARM |

Усі поля заголовків IP та ICMP передаються в **big-endian**. Це закріплено
в [RFC 791, Appendix B «Data Transmission Order»](https://www.rfc-editor.org/rfc/rfc791#appendix-B)
і в розділі «Data Notations» [RFC 1700](https://www.rfc-editor.org/rfc/rfc1700).
Якщо записати число в порядку процесора, отримувач прочитає інше значення.

### Модуль `struct`: числа ↔ байти

[`struct`](https://docs.python.org/3/library/struct.html) перетворює Python-значення
на байти й назад за **рядком формату**. Для заголовка ICMP використовуємо `"!BBHHH"`:

| Символ | Значення | Документація |
|---|---|---|
| `!` | мережевий порядок (big-endian), без вирівнювання | [Byte Order, Size, and Alignment](https://docs.python.org/3/library/struct.html#byte-order-size-and-alignment) |
| `B` | `unsigned char`, 1 байт, 0…255 | [Format Characters](https://docs.python.org/3/library/struct.html#format-characters) |
| `H` | `unsigned short`, 2 байти, 0…65535 | [Format Characters](https://docs.python.org/3/library/struct.html#format-characters) |

Тобто `B B H H H` відповідає полям Type, Code, Checksum, Identifier, Sequence.

```pycon
>>> import struct
>>> struct.pack("!BBHHH", 8, 0, 0, 0x1234, 1)
b'\x08\x00\x00\x00\x124\x00\x01'
>>> struct.pack("!BBHHH", 8, 0, 0, 0x1234, 1).hex(" ")
'08 00 00 00 12 34 00 01'
>>> struct.pack("<H", 0x1234).hex(" ")       # little-endian, для порівняння
'34 12'
>>> struct.calcsize("!BBHHH")
8
>>> struct.unpack("!BBHHH", bytes.fromhex("0800000012340001"))
(8, 0, 0, 4660, 1)
```

- [`struct.pack(format, v1, v2, ...)`](https://docs.python.org/3/library/struct.html#struct.pack) перетворює значення на [`bytes`](https://docs.python.org/3/library/stdtypes.html#bytes).
- [`struct.unpack(format, buffer)`](https://docs.python.org/3/library/struct.html#struct.unpack) робить зворотне перетворення і повертає кортеж.
- [`struct.calcsize(format)`](https://docs.python.org/3/library/struct.html#struct.calcsize) повертає розмір у байтах.

> Python друкує байт `0x34` як `4`, бо це ASCII-код символу «4». Тому `b'\x124'`
> означає два байти, `0x12` і `0x34`. Метод [`bytes.hex()`](https://docs.python.org/3/library/stdtypes.html#bytes.hex)
> показує байти однозначно.

### Internet Checksum (RFC 1071)

Контрольна сума дає змогу помітити пакет, пошкоджений у дорозі. Той самий алгоритм
використовують IPv4, ICMP, UDP і TCP. Його описано в
[RFC 1071, розд. 1](https://www.rfc-editor.org/rfc/rfc1071#section-1):

1. Розбити дані на **16-бітні слова** (пари байтів, big-endian). Якщо байтів непарна кількість, додати в кінець нульовий байт.
2. Скласти всі слова в арифметиці з **доповненням до одиниці** ([one's complement](https://en.wikipedia.org/wiki/Ones%27_complement)). На практиці це означає: рахувати звичайну суму, а потім переносити все, що вийшло за 16 біт, назад у молодші розряди («end-around carry»), доки сума не вміститься в 16 біт.
3. Результатом є **інверсія** суми (`~sum`), тобто кожен біт змінено на протилежний.

#### Приклад з RFC 1071, розд. 3

Дані: `00 01 f2 03 f4 f5 f6 f7`. Отже, слова: `0001`, `f203`, `f4f5`, `f6f7`.

```
  0x0001
+ 0xf203
+ 0xf4f5
+ 0xf6f7
--------
 0x2ddf0      ← звичайна сума, не вміщується в 16 біт

 0xddf0       ← молодші 16 біт  (total & 0xFFFF)
+0x0002       ← перенос         (total >> 16)
--------
 0xddf2       ← сума з доповненням до одиниці

~0xddf2 = 0x220d   ← контрольна сума
```

#### Як отримувач перевіряє пакет

Отримувач рахує ту саму суму по **всьому** пакету, разом із полем Checksum.
Якщо пакет не пошкоджено, `checksum(packet)` дає **0**. Тобто окремо
витягати поле не потрібно. Цю властивість ми перевіримо в тестах.

#### Реалізація

```python
def checksum(data: bytes) -> int:
    if len(data) % 2:
        data += b"\x00"

    total = 0
    for i in range(0, len(data), 2):
        total += (data[i] << 8) + data[i + 1]

    while total >> 16:
        total = (total & 0xFFFF) + (total >> 16)

    return ~total & 0xFFFF
```

| Вираз | Що робить | Документація |
|---|---|---|
| `len(data) % 2` | непарна довжина дає 1, тобто `True` | [`len`](https://docs.python.org/3/library/functions.html#len), [`%`](https://docs.python.org/3/reference/expressions.html#binary-arithmetic-operations) |
| `data[i]` | індексування `bytes` повертає **число** 0…255, а не символ | [`bytes`](https://docs.python.org/3/library/stdtypes.html#bytes) |
| `range(0, len(data), 2)` | 0, 2, 4, …: індекси початку кожного слова | [`range`](https://docs.python.org/3/library/stdtypes.html#range) |
| `data[i] << 8` | зсув на 8 біт вліво: старший байт слова | [shifting operations](https://docs.python.org/3/reference/expressions.html#shifting-operations) |
| `total & 0xFFFF` | залишає молодші 16 біт | [binary bitwise operations](https://docs.python.org/3/reference/expressions.html#binary-bitwise-operations) |
| `total >> 16` | усе, що вийшло за 16 біт (перенос) | [shifting operations](https://docs.python.org/3/reference/expressions.html#shifting-operations) |
| `~total & 0xFFFF` | інверсія бітів. Цілі числа в Python не мають фіксованого розміру, тому `~0xddf2` дає `-56819`, і `& 0xFFFF` обрізає результат до 16 біт. | [unary bitwise operations](https://docs.python.org/3/reference/expressions.html#unary-arithmetic-and-bitwise-operations) |

---

## Практика

### Крок 1. Константи

```python
ICMP_ECHO_REQUEST = 8
ICMP_ECHO_CODE = 0

ICMP_HEADER_FORMAT = "!BBHHH"
ICMP_HEADER_SIZE = struct.calcsize(ICMP_HEADER_FORMAT)  # 8 байтів

IP_HEADER_SIZE = 20          # RFC 791, розд. 3.1, заголовок без опцій
DEFAULT_PAYLOAD_SIZE = 56    # як у системного ping
```

Іменовані константи замість «магічних чисел» `8`, `20`, `56` пояснюють, звідки
взялося кожне значення. Розмір заголовка ми не прописуємо вручну, а обчислюємо
з формату. Тож якщо формат зміниться, розмір зміниться разом із ним.

### Крок 2. Дані пакета

```python
def build_payload(size: int) -> bytes:
    """Повертає дані пакета: байти 0x00, 0x01, 0x02, ... довжиною size."""
    return bytes(i & 0xFF for i in range(size))
```

Вміст даних може бути будь-яким. Але впізнаваний шаблон зручно бачити в
hex-дампі та під час налагодження. Системний ping теж заповнює дані
байтами, що зростають (див. функцію `setup()` у
[`ping_common.c`](https://github.com/iputils/iputils/blob/master/ping/ping_common.c)).

- [Генераторний вираз](https://docs.python.org/3/reference/expressions.html#generator-expressions) `(... for i in range(size))` створює числа по одному.
- [`bytes(iterable)`](https://docs.python.org/3/library/stdtypes.html#bytes) збирає з них об'єкт `bytes`. Кожне число має бути в межах 0…255, тому `i & 0xFF` замінює 256 на 0, 257 на 1 і так далі.

### Крок 3. Збираємо Echo Request

```python
def build_echo_request(identifier: int, sequence: int, payload: bytes) -> bytes:
    """Збирає ICMP Echo Request (RFC 792) з правильною контрольною сумою."""
    header = struct.pack(
        ICMP_HEADER_FORMAT, ICMP_ECHO_REQUEST, ICMP_ECHO_CODE, 0, identifier, sequence
    )
    csum = checksum(header + payload)
    header = struct.pack(
        ICMP_HEADER_FORMAT, ICMP_ECHO_REQUEST, ICMP_ECHO_CODE, csum, identifier, sequence
    )
    return header + payload
```

Пакет збирається у два проходи:

1. Пакуємо заголовок із `checksum = 0`, бо так вимагає RFC 792.
2. Рахуємо контрольну суму по заголовку **і даним** та пакуємо заголовок ще раз, уже з правильним значенням.

Байти з'єднуються оператором `+` ([операції над послідовностями](https://docs.python.org/3/library/stdtypes.html#common-sequence-operations)).

### Крок 4. Identifier

```python
identifier = os.getpid() & 0xFFFF
```

[`os.getpid()`](https://docs.python.org/3/library/os.html#os.getpid) повертає номер
поточного процесу (PID). Різні процеси мають різні PID, тому два одночасно запущені
ping не сплутають відповіді. PID може бути більшим за 65535 (див.
`/proc/sys/kernel/pid_max` у [`proc(5)`](https://man7.org/linux/man-pages/man5/proc_sys_kernel.5.html)),
а поле має лише 16 біт, тому `& 0xFFFF` залишає молодші 16 біт.

### Крок 5. Показуємо пакет

```python
def describe_packet(packet: bytes) -> str:
    type_, code, csum, identifier, sequence = struct.unpack(
        ICMP_HEADER_FORMAT, packet[:ICMP_HEADER_SIZE]
    )
    return (
        f"type={type_} code={code} checksum=0x{csum:04x} "
        f"id={identifier} seq={sequence} payload={len(packet) - ICMP_HEADER_SIZE} bytes"
    )


def hexdump(data: bytes, width: int = 16) -> str:
    lines = []
    for offset in range(0, len(data), width):
        chunk = data[offset : offset + width]
        lines.append(f"{offset:04x}  {chunk.hex(' ')}")
    return "\n".join(lines)
```

- `describe_packet` розбирає щойно зібраний пакет назад через [`struct.unpack`](https://docs.python.org/3/library/struct.html#struct.unpack). Так ми бачимо, що пакування й розпакування дають ті самі значення. Цей самий код знадобиться в уроці 3 для розбору відповіді.
- `packet[:ICMP_HEADER_SIZE]` — [зріз](https://docs.python.org/3/library/stdtypes.html#common-sequence-operations) перших 8 байтів.
- `type_` має підкреслення в кінці, бо `type` — вбудована функція Python ([PEP 8, Naming Styles](https://peps.python.org/pep-0008/#descriptive-naming-styles)).
- `{csum:04x}`, `{offset:04x}` — [специфікатор формату](https://docs.python.org/3/library/string.html#format-specification-mini-language): шістнадцятковий запис, доповнений нулями до 4 символів.
- [`bytes.hex(sep)`](https://docs.python.org/3/library/stdtypes.html#bytes.hex) — hex-рядок із роздільником між байтами.
- [`str.join`](https://docs.python.org/3/library/stdtypes.html#str.join) з'єднує рядки через `\n`.

### Крок 6. `main()`

```python
    payload_size = DEFAULT_PAYLOAD_SIZE
    total_size = payload_size + ICMP_HEADER_SIZE + IP_HEADER_SIZE
    print(f"PING {args.host} ({address}) {payload_size}({total_size}) bytes of data.")

    identifier = os.getpid() & 0xFFFF
    packet = build_echo_request(identifier, 1, build_payload(payload_size))

    print(describe_packet(packet))
    print(hexdump(packet))
```

Рядок-заголовок тепер збігається з виводом системного ping, а `56(84)` обчислено
з констант (розбір див. в [уроці 1](../01-cli-skeleton/README.md#рядок-заголовок)).

### Читаємо hex-дамп

```
0000  08 00 28 33 d8 b8 00 01 00 01 02 03 04 05 06 07
      ── ── ───── ───── ───── ───────────────────────
      │  │    │     │     │    └ Data: 00 01 02 ... (56 байтів, тривають до 0x37)
      │  │    │     │     └ Sequence Number = 0x0001 = 1
      │  │    │     └ Identifier = 0xd8b8 = 55480 (молодші 16 біт PID)
      │  │    └ Checksum = 0x2833
      │  └ Code = 0
      └ Type = 8 (Echo Request)
```

Identifier і checksum у вас будуть інші, бо PID змінюється з кожним запуском.

---

## Тести

Помилку в контрольній сумі важко помітити очима, а в уроці 3 вона проявиться лише
тим, що відповідь не прийде. Тому перевіряємо функції автоматично, модулем
[`unittest`](https://docs.python.org/3/library/unittest.html) зі стандартної бібліотеки.

```python
import unittest

from ping import ICMP_HEADER_FORMAT, build_echo_request, build_payload, checksum


class ChecksumTest(unittest.TestCase):
    def test_rfc1071_example(self) -> None:
        data = bytes.fromhex("0001f203f4f5f6f7")
        self.assertEqual(checksum(data), 0x220D)
    ...
```

- Тести — це методи класу-нащадка [`unittest.TestCase`](https://docs.python.org/3/library/unittest.html#unittest.TestCase), імена яких починаються з `test`.
- [`assertEqual(a, b)`](https://docs.python.org/3/library/unittest.html#unittest.TestCase.assertEqual) зупиняє тест з помилкою, якщо `a != b`.
- [`bytes.fromhex`](https://docs.python.org/3/library/stdtypes.html#bytes.fromhex) створює `bytes` з hex-рядка. Так тестові дані легко порівнювати з RFC.
- Тестові методи нічого не повертають, тому мають анотацію `-> None` ([PEP 484, «Using None»](https://peps.python.org/pep-0484/#using-none)). Без неї `mypy --strict` повідомить, що функцію не анотовано.
- `from ping import ...` працює, бо в `ping.py` запуск `main()` захищено умовою [`if __name__ == "__main__"`](https://docs.python.org/3/library/__main__.html) (урок 1).

Що перевіряємо:

| Тест | Що доводить |
|---|---|
| `test_rfc1071_example` | реалізація дає той самий результат, що й приклад з [RFC 1071, розд. 3](https://www.rfc-editor.org/rfc/rfc1071#section-3) |
| `test_odd_length_is_padded_with_zero` | непарна довжина обробляється за правилом RFC |
| `test_empty_data` | крайній випадок: сума 0, отже інверсія дорівнює `0xFFFF` |
| `test_header_fields` | поля стоять на своїх місцях |
| `test_known_checksum` | точний байтовий вміст мінімального пакета, порахований вручну |
| `test_checksum_of_valid_packet_is_zero` | пакет пройде перевірку отримувача ([RFC 1071, розд. 1](https://www.rfc-editor.org/rfc/rfc1071#section-1)) |
| `test_packet_length` | 8 + 56 = 64 байти |

Запуск ([інтерфейс командного рядка unittest](https://docs.python.org/3/library/unittest.html#command-line-interface)):

```console
$ python3 -m unittest -v
test_empty_data (test_ping.ChecksumTest.test_empty_data) ... ok
test_odd_length_is_padded_with_zero (test_ping.ChecksumTest.test_odd_length_is_padded_with_zero) ... ok
test_rfc1071_example (test_ping.ChecksumTest.test_rfc1071_example) ... ok
test_checksum_of_valid_packet_is_zero (test_ping.EchoRequestTest.test_checksum_of_valid_packet_is_zero) ... ok
test_header_fields (test_ping.EchoRequestTest.test_header_fields) ... ok
test_known_checksum (test_ping.EchoRequestTest.test_known_checksum) ... ok
test_packet_length (test_ping.EchoRequestTest.test_packet_length) ... ok

----------------------------------------------------------------------
Ran 7 tests in 0.001s

OK
```

### Перевірка типів

```console
$ ../.venv/bin/mypy --strict ping.py test_ping.py
Success: no issues found in 2 source files
```

Тепер mypy перевіряє і тести. Наприклад, виклик `checksum("abc")` з рядком замість
`bytes` mypy позначить як помилку `arg-type` ще до запуску. Під час виконання такий
виклик впаде лише всередині `checksum()` з повідомленням
`TypeError: can only concatenate str (not "bytes") to str`, з якого причину не видно.

## Повний код

- [`ping.py`](ping.py) — програма
- [`test_ping.py`](test_ping.py) — тести

## Використані функції та модулі

| Що | Документація |
|---|---|
| `struct.pack` | <https://docs.python.org/3/library/struct.html#struct.pack> |
| `struct.unpack` | <https://docs.python.org/3/library/struct.html#struct.unpack> |
| `struct.calcsize` | <https://docs.python.org/3/library/struct.html#struct.calcsize> |
| Формат `struct`: порядок байтів | <https://docs.python.org/3/library/struct.html#byte-order-size-and-alignment> |
| Формат `struct`: символи | <https://docs.python.org/3/library/struct.html#format-characters> |
| `os.getpid` | <https://docs.python.org/3/library/os.html#os.getpid> |
| `bytes` | <https://docs.python.org/3/library/stdtypes.html#bytes> |
| `bytes.hex` | <https://docs.python.org/3/library/stdtypes.html#bytes.hex> |
| `bytes.fromhex` | <https://docs.python.org/3/library/stdtypes.html#bytes.fromhex> |
| `range` | <https://docs.python.org/3/library/stdtypes.html#range> |
| `len` | <https://docs.python.org/3/library/functions.html#len> |
| `str.join` | <https://docs.python.org/3/library/stdtypes.html#str.join> |
| Зрізи та `+` для послідовностей | <https://docs.python.org/3/library/stdtypes.html#common-sequence-operations> |
| Бітові операції `&`, `\|` | <https://docs.python.org/3/reference/expressions.html#binary-bitwise-operations> |
| Зсуви `<<`, `>>` | <https://docs.python.org/3/reference/expressions.html#shifting-operations> |
| Інверсія `~` | <https://docs.python.org/3/reference/expressions.html#unary-arithmetic-and-bitwise-operations> |
| Генераторні вирази | <https://docs.python.org/3/reference/expressions.html#generator-expressions> |
| Специфікатори формату (`:04x`) | <https://docs.python.org/3/library/string.html#format-specification-mini-language> |
| `unittest.TestCase` | <https://docs.python.org/3/library/unittest.html#unittest.TestCase> |
| `TestCase.assertEqual` | <https://docs.python.org/3/library/unittest.html#unittest.TestCase.assertEqual> |
| `unittest.main` | <https://docs.python.org/3/library/unittest.html#unittest.main> |
| `python -m unittest` | <https://docs.python.org/3/library/unittest.html#command-line-interface> |

Функції з уроку 1 (`argparse`, `socket.getaddrinfo`, `sys.exit` …) описано
в [уроці 1](../01-cli-skeleton/README.md#використані-функції-та-модулі).

## Вправи

1. Порахуйте вручну контрольну суму пакета `type=8 code=0 id=0x0001 seq=0x0002` без даних. Перевірте результат через `checksum()`.
2. Змініть у готовому пакеті один байт даних і виконайте `checksum(packet)`. Чому результат більше не 0?
3. Поміняйте місцями два 16-бітні слова в даних. Чи змінилася контрольна сума? Що це говорить про те, які пошкодження ця сума **не** виявляє? (Підказка: [RFC 1071, розд. 2(B)](https://www.rfc-editor.org/rfc/rfc1071#section-2).)
4. Замініть `"!BBHHH"` на `"<BBHHH"` і запустіть тести. Які впали і чому?
5. Подивіться на справжній пакет системного ping: у першому терміналі запустіть `sudo tcpdump -i any -X -c 2 icmp` ([`tcpdump(1)`](https://www.tcpdump.org/manpages/tcpdump.1.html)), у другому — `ping -c 1 example.com`. Знайдіть у дампі заголовок IPv4 (20 байтів), Type, Code, Checksum, Identifier і Sequence. Чим дані системного ping відрізняються від наших? (Підказка: перші 16 байтів даних — це [`struct timeval`](https://man7.org/linux/man-pages/man3/timeval.3type.html), час відправки.)

## Джерела

- [RFC 792](https://www.rfc-editor.org/rfc/rfc792) — ICMP, формат Echo / Echo Reply (с. 14)
- [RFC 1071](https://www.rfc-editor.org/rfc/rfc1071) — Computing the Internet Checksum
- [RFC 791, Appendix B](https://www.rfc-editor.org/rfc/rfc791#appendix-B) — порядок передачі даних (big-endian)
- [RFC 1122, розд. 3.2.2.6](https://www.rfc-editor.org/rfc/rfc1122#section-3.2.2.6) — Echo Request/Reply: вимоги до хоста
- [IANA ICMP Parameters](https://www.iana.org/assignments/icmp-parameters/icmp-parameters.xhtml) — реєстр типів і кодів
- [iputils `ping_common.c`](https://github.com/iputils/iputils/blob/master/ping/ping_common.c) — як дані заповнює системний ping
