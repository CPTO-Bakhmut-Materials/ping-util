"""Дає змогу запускати пакет командою: python3 -m pyping example.com"""

import sys

from .cli import main

sys.exit(main())
