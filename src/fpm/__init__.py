import logging


class AnsiColorFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord):
        no_style = "\033[0m"
        bold = "\033[91m"
        grey = "\033[90m"
        yellow = "\033[93m"
        red = "\033[31m"
        red_light = "\033[91m"
        blue = "\033[34m"
        start_style = {
            "DEBUG": grey,
            "INFO": no_style,
            "WARNING": yellow,
            "ERROR": red_light,
            "CRITICAL": red + bold,
        }.get(record.levelname, no_style)
        end_style = no_style
        return f"{start_style}{super().format(record)}{end_style}"


logger = logging.getLogger("floorplan")
logger.setLevel(logging.INFO)
fh = logging.FileHandler("floorplan-cli.log")
fh.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
file_formatter = logging.Formatter(
    "{asctime} | {levelname:<8s} | {name:<30s} | {message}",
    style="{",
)
console_formatter = AnsiColorFormatter(
    "{asctime} | {levelname:<8s} | {name:<30s} | {message}",
    style="{",
)
# ch.setFormatter(console_formatter)
fh.setFormatter(file_formatter)
logger.addHandler(ch)
logger.addHandler(fh)
