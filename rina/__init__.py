import logging


class Config:
    DRYRUN: bool = False
    YES: bool = False


def set_logger(verbose: bool):
    logger = logging.getLogger(__name__)
    handler = logging.StreamHandler()
    if verbose:
        format = "%(levelname)s [%(name)s]: %(message)s"
        logger.setLevel(logging.DEBUG)
    else:
        format = "%(levelname)s: %(message)s"
    handler.setFormatter(logging.Formatter(format))
    logger.addHandler(handler)
    logger.debug(f"Added a stderr logging handler to logger: {__name__}")
