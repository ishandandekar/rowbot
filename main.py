import anyio

from frontend.app import run_tui_app
from shared.models import DEFAULT_BACKEND_URL


def main() -> None:
    anyio.run(lambda: run_tui_app(backend_url=DEFAULT_BACKEND_URL))


if __name__ == "__main__":
    main()
