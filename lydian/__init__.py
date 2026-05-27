from loguru import logger  # noqa: D104

__version__ = '0.7.0'

logger.remove()

logger.level('WARNING', color='<yellow>')
logger.level('ERROR', color='<red>')
