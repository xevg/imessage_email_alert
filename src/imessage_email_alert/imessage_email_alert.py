import logging
import sys
import time
from pathlib import Path
from typing import Optional

from .get_email_message import GetEmailMessage, DeleteError
from .send_imessage import SendImessage
from icecream import ic

ic.configureOutput(includeContext=True)


class iMessageEmailAlert:
    message_length = 1000  # The maximum message length to send

    def __init__(
        self,
        phone_number: str,
        credentials_file: str = None,
        token_file: str = None,
        log_dir: Path = None,
        debug: bool = False,
    ):
        self.phone_number = phone_number
        self.credential_files = credentials_file
        self.token_file = token_file
        self.log_dir = log_dir
        self.debug = debug

        self.gmail: Optional[GetEmailMessage] = None
        self.imessage = SendImessage(self.phone_number)

        app_name = "iMessageEmailAlert"
        log_format: str = "%(asctime)s [%(process)d] <%(name)s> %(message)s"
        date_format: str = "%Y-%m-%d %I:%M:%S %p"
        self.logger = logging.getLogger(app_name)
        self.logger.setLevel(logging.INFO)
        logging.Formatter(log_format, datefmt=date_format)

        if self.log_dir is not None:
            file_handler = logging.FileHandler(
                f"{self.log_dir / app_name}.log", mode="a"
            )
            file_handler.setFormatter(
                logging.Formatter(log_format, datefmt=date_format)
            )
            self.logger.addHandler(file_handler)

        if self.debug:
            stdout_handler = logging.StreamHandler(sys.stdout)
            stdout_handler.setFormatter(
                logging.Formatter(log_format, datefmt=date_format)
            )
            self.logger.addHandler(stdout_handler)

        self.logger.info("Starting Email Alert Service")

    def process_messages(self):
        while True:
            try:
                self.gmail = GetEmailMessage(self.credential_files, self.token_file)
                break
            except Exception as error:
                error_string = f"An error occurred with authorization:" f" {error}"
                self.imessage.send_message(error_string)
                self.logger.error(error_string)
                ic(error_string)
                time.sleep(60 * 10)  # 10 minutes so I don't flood the texts overnight

        while True:
            try:
                message = self.gmail.get_next_message()
            except Exception as error:
                error_string = f"An error occurred trying to get mail:" f" {error}"
                self.imessage.send_message(error_string)
                self.logger.error(error_string)
                ic(error_string)
                time.sleep(60 * 10)  # 10 minutes so I don't flood the texts overnight
                continue

            if message:
                try:
                    # Massage message to the format I want
                    text = message.body
                    text = text.replace("\r\n", "\n")
                    text = text.replace("\u200c", "")
                    new_text = []
                    for line in text.split("\n"):
                        line = line.strip()
                        if line != "":
                            new_text.append(line)

                    text = "\n\n".join(new_text)
                    """
                    while "\n\n" in text:  # Get rid of multiple carriage returns
                        text = text.replace("\n\n", "\n")
                    text = text.replace("\n", "\n\n")
                    """
                    if (
                        len(text) > self.message_length
                    ):  # Shorten the message to fit into a text
                        text = f"{text[:self.message_length]}\n\n........"

                    message_text = (
                        f"To: {message.to_email}\nSubject: "
                        f"{message.subject}\n\n{text}"
                    )

                    self.imessage.send_message(message_text)
                    self.logger.info(
                        f"Message sent to {message.to_email}: " f"{message.subject}"
                    )
                except Exception as error:
                    error_string = f"An error occurred trying to send message:{error}"

                    # self.imessage.send_message(error_string)
                    self.logger.error(error_string)
                    ic(error_string)
                    time.sleep(
                        60 * 10
                    )  # 10 minutes so I don't flood the texts overnight
                    continue

                try:
                    self.gmail.delete_message(message.message_id)
                except Exception as error:
                    error_string = f"An error occurred trying to delete message:{error}"

                    self.imessage.send_message(error_string)
                    self.logger.error(error_string)
                    ic(error_string)

            time.sleep(10)
