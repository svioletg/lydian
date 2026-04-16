from loguru import logger  # noqa: D104

logger.remove()

logger.level('WARNING', color='<yellow>')
logger.level('ERROR', color='<red>')
