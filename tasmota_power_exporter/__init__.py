from tasmota_power_exporter.metrics import run_exporter


def run_cli() -> None:
    # Entrypoint for CLI
    run_exporter()
