"""Урок 8: точка входу. Уся логіка тепер у пакеті pyping.

Запуск такий самий, як у попередніх уроках: sudo python3 ping.py example.com
"""

import sys

from pyping.cli import main

if __name__ == "__main__":
    sys.exit(main())
