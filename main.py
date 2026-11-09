import logfire
from src.app import run_tui_app

logfire.configure(send_to_logfire="if-token-present")
logfire.instrument_system_metrics()
logfire.instrument_pydantic_ai()


def main() -> None:
    run_tui_app()


if __name__ == "__main__":
    main()
