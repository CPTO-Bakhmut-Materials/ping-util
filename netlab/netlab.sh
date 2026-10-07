#!/bin/sh
# Тестова мережа для курсу. Права root НЕ потрібні.
#
# Створює ізольовані мережеві простори імен (network namespaces):
#
#   [клієнт 10.0.0.1] --veth-- [маршрутизатор 10.0.0.2 | 10.1.0.1] --> 10.1.0.0/24 (dummy)
#
# і запускає команду в «клієнті». Усередині ми root у власному user namespace,
# тому raw-сокети працюють без sudo і не впливають на справжню мережу.
#
# Що можна перевірити:
#   10.0.0.2, 10.1.0.1   відповідають на ping
#   10.1.0.99            пакети зникають без відповіді (тайм-аут)
#   10.1.0.99 з -t 1     маршрутизатор повертає Time to live exceeded
#   10.9.9.9             маршрутизатор повертає Destination Net Unreachable
#   10.0.0.77            клієнт сам повертає Destination Host Unreachable (через ~3 с)
#
# Використання (з кореня репозиторію):
#   ./netlab/netlab.sh 'python3 03-first-ping/ping.py 10.0.0.2'
#   ./netlab/netlab.sh          # інтерактивна оболонка всередині мережі (вихід: exit)
#
# Файли:
#   netlab.sh   цей скрипт: створює простори імен клієнта і запускає client.sh
#   client.sh   налаштовує клієнта, запускає маршрутизатор і виконує команду
#   router.sh   налаштовує маршрутизатор

NETLAB_DIR=$(dirname "$(readlink -f "$0")")
export NETLAB_DIR

COMMAND="${1:-${SHELL:-/bin/sh}}"

exec unshare --map-root-user --net "$NETLAB_DIR/client.sh" "$COMMAND"
