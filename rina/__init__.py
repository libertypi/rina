import logging


def config_logger(verbose: bool = False):
    """
    Configures the logging settings for this package.

    This method needs to be in this __init__.py to get the __name__ correct.
    """
    logger = logging.getLogger(__name__)
    # Clear existing handlers
    logger.handlers.clear()
    # Set the logging format based on the verbosity
    if verbose:
        format = "[%(levelname)s] %(name)s: %(message)s"
        logger.setLevel(logging.DEBUG)
    else:
        format = "[%(levelname)s] %(message)s"
        logger.setLevel(logging.WARNING)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(format))
    logger.addHandler(handler)
    logger.propagate = False
