import logfire

from src.tui import run_tui_app

logfire.configure(send_to_logfire="if-token-present")
logfire.instrument_system_metrics()
logfire.instrument_pydantic_ai()


if __name__ == "__main__":
    run_tui_app()
