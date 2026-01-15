import logging

from logging.handlers import RotatingFileHandler


def configure_logging():
    log_format = '[%(asctime)s] - %(levelname)s %(name)s - %(message)s'

    logging.basicConfig(
        level=logging.WARNING,
        format=log_format,  # Формат сообщений
        handlers=[
            RotatingFileHandler('logs/bot.log', maxBytes=10 * 1024 * 1024, backupCount=3, encoding='utf-8'),
            logging.StreamHandler()  # Вывод в консоль
        ]
    )

    error_handler = RotatingFileHandler('logs/errors_bot.log', maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8')
    error_handler.setLevel(logging.ERROR)  # Только ERROR и выше
    error_formatter = logging.Formatter(log_format)
    error_handler.setFormatter(error_formatter)

    logging.getLogger().addHandler(error_handler)

