import sys

import graypy
import logging

from config.Config import CONFIG
from utils.context_var import request_id_var


class GraylogFormatter(logging.Formatter):
    def format(self, record):
        # Добавляем app_name как дополнительное поле
        record.app_name = CONFIG.logging.app_name
        record.request_id = request_id_var.get()
        return super().format(record)


if CONFIG.logging.graylog.enabled:
    if CONFIG.logging.graylog.udp:
        graylog_handler = graypy.GELFUDPHandler(
            CONFIG.logging.graylog.host, CONFIG.logging.graylog.port
        )
    else:
        graylog_handler = graypy.GELFTCPHandler(
            CONFIG.logging.graylog.host, CONFIG.logging.graylog.port
        )

    graylog_formatter = GraylogFormatter("[%(name)s]: %(message)s")
    graylog_handler.setFormatter(graylog_formatter)
else:
    graylog_handler = None

if CONFIG.logging.console.enabled:
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    )
else:
    console_handler = None

logging.getLogger().setLevel(logging.getLevelName(CONFIG.logging.root_level))
for log, level in CONFIG.logging.levels.items():
    logging.getLogger(log).setLevel(logging.getLevelName(level))


def get_logger(name) -> logging:
    logger = logging.getLogger(name)

    logger.propagate = False  # Global logger should not print messages again.

    # Avoiding log duplicates: do not add handlers again to already initialized logger
    # https://stackoverflow.com/questions/7173033/duplicate-log-output-when-using-python-logging-module
    if len(logger.handlers) != 0:
        return logger

    if console_handler:
        logger.addHandler(console_handler)

    if graylog_handler:
        logger.addHandler(graylog_handler)

    return logger


def get_logger_univorn():
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "handlers": {
            "console": {
                "()": lambda: console_handler,
            }
        },
        "root": {
            "level": "INFO",
            "handlers": ["console"],
        },
    }
    if CONFIG.logging.graylog.enabled:
        logging_config["handlers"]["graylog"] = {
            "()": lambda: graylog_handler,
        }
        logging_config["root"]["handlers"].append("graylog")
    return logging_config
