from .log_config import setup_logging
import logging
import click

setup_logging()

logger = logging.getLogger(__name__)

@click.command()
def main():
    logger.info("TestDataGen CLI started...")
