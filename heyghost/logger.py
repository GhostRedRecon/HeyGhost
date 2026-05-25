import logging
from pathlib import Path


def configure_logging(level: str, log_file: str) -> logging.Logger:
    logger = logging.getLogger("heyghost")
    if logger.handlers:
        return logger

    resolved_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(resolved_level)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    try:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        logger.warning("Could not open log file %s", log_file)

    return logger
