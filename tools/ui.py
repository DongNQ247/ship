import sys


RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
CYAN = "\033[0;36m"
BOLD = "\033[1m"
NC = "\033[0m"


def print_err(message: str) -> None:
    print(message, file=sys.stderr)


def die(message: str, code: int = 1) -> None:
    print_err(message)
    raise SystemExit(code)

