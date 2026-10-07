#!/bin/sh
# Маршрутизатор тестової мережі. client.sh запускає цей скрипт через nsenter
# у мережевому просторі імен маршрутизатора, куди вже переміщено інтерфейс b0.

set -e
ip link set lo up
ip addr add 10.0.0.2/24 dev b0
ip link set b0 up

# dummy-інтерфейс: мережа 10.1.0.0/24 існує, але пакети туди зникають.
ip link add d0 type dummy
ip addr add 10.1.0.1/24 dev d0
ip link set d0 up

# Маршрутизатор пересилає пакети між інтерфейсами.
echo 1 > /proc/sys/net/ipv4/ip_forward
