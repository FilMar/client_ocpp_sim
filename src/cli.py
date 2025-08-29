import asyncio
import logging

import click

from .client import start_client


@click.group()
def main():
    pass


@main.command()
@click.argument("ws_url", type=str)
@click.option(
    "--cp-id",
    default="CP001",
    help="Charge Point identifier.",
)
@click.option(
    "--vendor",
    default="AcmeCorp",
    help="The manufacturer's name.",
)
@click.option(
    "--model",
    default="ModelX",
    help="The station model.",
)
@click.option(
    "--firmware",
    default=None,
    help="The firmware version.",
)
@click.option(
    "--connectors",
    default=2,
    help="The number of connectors.",
)
@click.option(
    "--log-level",
    default="INFO",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    help="Sets the logging level.",
)
def run(ws_url, cp_id, vendor, model, firmware, connectors, log_level):
    """
    Starts the OCPP client simulator.

    WS_URL: The WebSocket URL of the CSMS.
    """
    logging.basicConfig(level=log_level)
    logging.info(f"Starting Charge Point '{cp_id}'...")

    # Configure ocpp logger to write to a file
    ocpp_logger = logging.getLogger("ocpp")
    file_handler = logging.FileHandler("ocpp.log")
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    ocpp_logger.addHandler(file_handler)
    ocpp_logger.propagate = False

    asyncio.run(start_client(ws_url, cp_id, vendor, model, firmware, connectors))


if __name__ == "__main__":
    main()
