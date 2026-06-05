from loguru import logger  # noqa: D104
from packaging.version import Version

__version__ = '0.8.0'

Version(__version__) # Raises InvalidVersion if __version__ doesn't match Python's packaging version scheme

logger.remove()

logger.level('WARNING', color='<yellow>')
logger.level('ERROR', color='<red>')
