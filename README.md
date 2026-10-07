# Пишемо ping на Python

Курс із 8 уроків. За цей час ми поступово напишемо власну версію утиліти
[`ping`](https://man7.org/linux/man-pages/man8/ping.8.html) мовою Python.
Кожен урок додає до програми одну нову можливість. Після кожного уроку
програма запускається і щось робить.

## Правила курсу

- **Тільки стандартна бібліотека Python.** Сторонні пакети (`scapy`, `ping3`, `icmplib` тощо) не використовуємо.
- **Кожен урок самодостатній.** У папці уроку лежить опис (`README.md`) і **повний** код на кінець уроку. Тому можна відкрити будь-який урок і запустити його окремо.
- **Кожне поняття має джерело.** Для протоколів подано посилання на RFC, для функцій Python — на документацію.
- **Анотації типів скрізь.** Кожна функція має type hints, і код кожного уроку проходить `mypy --strict`. mypy — інструмент розробника, програма від нього не залежить ([урок 1, крок 4](01-cli-skeleton/README.md#крок-4-анотації-типів-type-hints)).

## Вимоги

| Що | Версія | Чому |
|---|---|---|
| ОС | Linux | Поведінка ICMP-сокетів залежить від ОС. Курс перевірено на Linux ([`icmp(7)`](https://man7.org/linux/man-pages/man7/icmp.7.html), [`raw(7)`](https://man7.org/linux/man-pages/man7/raw.7.html)). |
| Python | 3.10 або новіший | Анотації виду `list[str] \| None` ([PEP 604](https://peps.python.org/pep-0604/)), [f-рядки](https://docs.python.org/3/reference/lexical_analysis.html#f-strings), [`bytes.hex(sep)`](https://docs.python.org/3/library/stdtypes.html#bytes.hex), а в уроці 7 — [`dataclasses`](https://docs.python.org/3/library/dataclasses.html). |
| mypy | будь-яка свіжа | Перевірка анотацій типів. Встановлюється у віртуальне середовище `.venv` ([урок 1](01-cli-skeleton/README.md#перевіряємо-типи-за-допомогою-mypy)). |
| Права | `sudo` з уроку 3 **або** [`netlab.sh`](netlab.sh) | Raw-сокет може відкрити лише root або процес із правом `CAP_NET_RAW` ([`capabilities(7)`](https://man7.org/linux/man-pages/man7/capabilities.7.html)). Тестова мережа `netlab.sh` дає змогу обійтися без root. |
| `iproute2`, `util-linux` | будь-які | Команди `ip`, `unshare`, `nsenter` для `netlab.sh`. Зазвичай уже встановлені. |

### Який сокет ми використовуємо

Відправити ICMP-пакет із Python можна двома способами:

1. **`SOCK_RAW`** ([`raw(7)`](https://man7.org/linux/man-pages/man7/raw.7.html)). Цей спосіб обрано для курсу. Він потребує root, але у відповідь ми отримуємо **увесь IP-пакет разом із заголовком**. Це дає змогу на практиці розібрати заголовок IPv4 ([RFC 791](https://www.rfc-editor.org/rfc/rfc791)) і дістати з нього TTL.
2. **`SOCK_DGRAM` + `IPPROTO_ICMP`**, так званий «ping socket» ([`icmp(7)`](https://man7.org/linux/man-pages/man7/icmp.7.html)). Він працює без root, якщо група користувача входить у діапазон `net.ipv4.ping_group_range` ([документація ядра](https://docs.kernel.org/networking/ip-sysctl.html)). Але ядро саме підставляє identifier і віддає лише ICMP-частину пакета. Цей варіант розглянемо як вправу.

## План

| № | Урок | Що додаємо | Стан |
|---|---|---|---|
| 1 | [Скелет CLI і знайомство з ping](01-cli-skeleton/README.md) | Розбираємо вивід системного `ping`. Аргументи командного рядка через `argparse`. Перетворення імені на адресу через `getaddrinfo`. Коди завершення. Анотації типів і mypy. | ✅ |
| 2 | [Пакет ICMP Echo Request](02-icmp-packet/README.md) | Структура заголовка ICMP. Пакування байтів через `struct`. Контрольна сума за RFC 1071. Перші тести на `unittest`. | ✅ |
| 3 | [Перший справжній ping](03-first-ping/README.md) | Raw-сокет: відправляємо один пакет, отримуємо Echo Reply. Розбираємо заголовок IPv4 і вимірюємо час обміну (RTT). | ✅ |
| 4 | [Надійність](04-reliability/README.md) | Тайм-аут очікування. Відкидаємо чужі пакети за id/seq. Перевіряємо контрольну суму відповіді. Обробляємо `PermissionError`. | ✅ |
| 5 | [Цикл](05-loop/README.md) | Опції `-c count` та `-i interval`, номер послідовності, коректне завершення за Ctrl+C. | ✅ |
| 6 | [Статистика](06-statistics/README.md) | Підсумковий блок: transmitted/received, % втрат, min/avg/max/mdev. | ✅ |
| 7 | [Рефакторинг](07-refactoring/README.md) | Розбиваємо код на пакет `pyping` (`packet.py`, `socket_io.py`, `pinger.py`, `stats.py`, `cli.py`). Додаємо `dataclasses`, `typing.Protocol`, `logging`, тести з mock. | ✅ |
| 8 | [ICMP-помилки й опції](08-errors-and-options/README.md) | Обробляємо Destination Unreachable і Time Exceeded. Додаємо опції `-t ttl`, `-s size`, `-W timeout`. Цей урок показує, наскільки легше розширювати код після рефакторингу. | ✅ |

Як змінюється код:

| Урок | Файли коду | Тестів | Що вміє |
|---|---|---|---|
| 1 | `ping.py` (57 рядків) | — | `PING host (ip)` |
| 2 | `ping.py` (140) | 7 | збирає пакет |
| 3 | `ping.py` (171) | 11 | один запит → одна відповідь |
| 4 | `ping.py` (230) | 11 | тайм-аут, фільтрація, помилки |
| 5 | `ping.py` (280) | 16 | цикл, `-c`, `-i`, Ctrl+C |
| 6 | `ping.py` (337) | 22 | повна статистика |
| 7 | пакет `pyping/` (6 модулів) | 27 | те саме + `-v`; логіка під тестами з mock |
| 8 | пакет `pyping/` (6 модулів) | 35 | ICMP-помилки, `-t`, `-s`, `-W`: вивід збігається з системним ping |

## Тестова мережа

Уроки 3–8 потребують raw-сокета, тобто root. Щоб не запускати навчальний код через
`sudo` і щоб відтворити ситуації, які в справжній мережі трапляються випадково
(тайм-аут, TTL exceeded, недоступна мережа), курс має скрипт [`netlab.sh`](netlab.sh).
Він створює ізольовану віртуальну мережу з маршрутизатором **без прав root**:

```console
$ ./netlab.sh 'python3 08-errors-and-options/ping.py -c 1 -t 1 10.1.0.99'
PING 10.1.0.99 (10.1.0.99) 56(84) bytes of data.
From 10.0.0.2 icmp_seq=1 Time to live exceeded
...
```

Схема мережі та як вона працює — в [уроці 8](08-errors-and-options/README.md#тестова-мережа-netlabsh).

## Як запускати

```bash
# один раз: середовище з mypy
python3 -m venv .venv
.venv/bin/pip install mypy

cd 01-cli-skeleton
python3 ping.py example.com

# з уроку 3 потрібні права root…
sudo python3 ping.py example.com
# …або тестова мережа без root
../netlab.sh 'python3 ping.py 10.0.0.2'

# тести (з уроку 2; в уроках 7–8 знаходять папку tests/ автоматично)
python3 -m unittest -v

# перевірка типів
../.venv/bin/mypy --strict .
```

## Основні джерела

| Документ | Про що |
|---|---|
| [RFC 792](https://www.rfc-editor.org/rfc/rfc792) | Internet Control Message Protocol (ICMP): формат усіх повідомлень, які використовує ping |
| [RFC 791](https://www.rfc-editor.org/rfc/rfc791) | Internet Protocol (IPv4): заголовок IP-пакета, TTL, порядок байтів |
| [RFC 1071](https://www.rfc-editor.org/rfc/rfc1071) | Обчислення Internet Checksum |
| [RFC 1812](https://www.rfc-editor.org/rfc/rfc1812) | Вимоги до маршрутизаторів: як вони генерують ICMP-помилки |
| [RFC 1122, розд. 3.2.2](https://www.rfc-editor.org/rfc/rfc1122#section-3.2.2) | Вимоги до того, як хост обробляє ICMP, зокрема Echo (3.2.2.6) |
| [IANA ICMP Parameters](https://www.iana.org/assignments/icmp-parameters/icmp-parameters.xhtml) | Офіційний реєстр типів і кодів ICMP |
| [`ping(8)`](https://man7.org/linux/man-pages/man8/ping.8.html) | Документація системної утиліти ping |
| [iputils](https://github.com/iputils/iputils) | Вихідний код ping, який стоїть у більшості дистрибутивів Linux |
| [`socket`](https://docs.python.org/3/library/socket.html) | Модуль Python для роботи з мережею |
