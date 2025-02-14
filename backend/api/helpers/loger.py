import logging
from logging.handlers import RotatingFileHandler
import os
import colorlog 


def init_logger():
    logging.basicConfig(level=logging.NOTSET)
    # Створення папки для логів, якщо вона не існує
    log_directory = os.path.join("/app/backend/api", "logs")
    os.makedirs(log_directory, exist_ok=True)

    # Повний шлях до файлу логів
    log_file = os.path.join(log_directory, "out_products.log")

    # Налаштування форматера для консолі (з кольорами)
    console_formatter = colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        }
    )

    # Налаштування форматера для файлу (без кольорів)
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Налаштування обробників
    file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3)
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.DEBUG)  # Логи від DEBUG і вище для файлу

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.DEBUG)  # Логи від DEBUG і вище для консолі

    # Налаштування логера для цього модуля
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)  # Логер пропускає всі рівні від DEBUG і вище
    # Перевірка, щоб уникнути дублювання обробників
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger

my_logger = init_logger()
my_logger.debug("Логер ініціалізований у loger.py")
my_logger.warning("Логер ініціалізований у loger.py")