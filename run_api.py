"""Inicializador usado pelo LetrasBR.exe e pelos scripts .bat (equivale a `python -m letrasbr_api`)."""

import sys

from letrasbr_api.app import main

if __name__ == "__main__":
    sys.exit(main())
