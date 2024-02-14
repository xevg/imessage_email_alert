import logging
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from icecream import ic

from .get_email_message import GetEmailMessage
from .send_imessage import SendImessage


class iMessageEmailAlert:
    """
    Send an iMessage alert every time a message comes in to gmail.
    The way I set this up is that for every message that I get im my email that
    I care about, I send a copy to dummy gmail account. This program retrieves the
    message from the dummy gmail account, sends it via iMessage, and then deletes it.
    """

    # The max lengh of the iMessage
    message_length = 800  # The maximum message length to send

    def __init__(
        self,
        phone_number: str,
        credentials_file: str = None,
        token_file: str = None,
        log_dir: Path = None,
        debug: bool = False,
    ):
        """
        :param phone_number: The phone number or email address of the iMessage
        recipient
        :param credentials_file: The location of the gmail credentials file
        :param token_file: The location to save the gmail token file
        :param log_dir: The location to store the logs
        :param debug: Debug mode
        """
        self.phone_number = phone_number
        self.credential_files = credentials_file
        self.token_file = token_file
        self.log_dir = log_dir
        self.debug = debug

        # The URLs in email messages have a lot of extraneous tracking stuff. For the
        # iMessage, I don't really care about those, so just shorten it to the main
        # part of the URL
        self.http_match = re.compile("(.*)(http[s]*://[^?]*)\?[\S]*(.*)$")

        self.gmail: Optional[GetEmailMessage] = None
        self.imessage = SendImessage(self.phone_number)

        app_name = "iMessageEmailAlert"
        log_format: str = "%(asctime)s [%(process)d] <%(name)s> %(message)s"
        date_format: str = "%Y-%m-%d %I:%M:%S %p"

        # Configure the ic output
        ic.configureOutput(
            includeContext=True,
            prefix=f'imessage_email_alert - {datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")}',
        )

        # Set up logging
        self.logger = logging.getLogger(app_name)
        self.logger.setLevel(logging.INFO)
        logging.Formatter(log_format, datefmt=date_format)

        if self.log_dir is None:
            self.log_dir = Path.home() / "logs"
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(
                f"{self.log_dir / app_name}.log", mode="a"
            )
            file_handler.setFormatter(
                logging.Formatter(log_format, datefmt=date_format)
            )
            self.logger.addHandler(file_handler)
        except Exception as exp:
            ic(f"Error setting up logfile: {exp}")

        if self.debug:
            stdout_handler = logging.StreamHandler(sys.stdout)
            stdout_handler.setFormatter(
                logging.Formatter(log_format, datefmt=date_format)
            )
            self.logger.addHandler(stdout_handler)

        self.logger.info("Starting Email Alert Service")

    def process_messages(self):
        """
        This is the main loop, checking for new messages, and processing them one at
        a time
        """
        # First connect to gmail, and create the GetEmailMessage instance
        while True:
            try:
                # Get the next gmail message
                self.gmail = GetEmailMessage(self.credential_files, self.token_file)
                break
            except Exception as error:
                # When an error occurs, sleep for a while and try again
                error_string = f"An error occurred with authorization:" f" {error}"
                self.imessage.send_message(error_string)
                self.logger.error(error_string)
                ic(error_string)
                time.sleep(60 * 10)  # 10 minutes so I don't flood the texts overnight

        # Once I have the gmail connection successfully, start grabbing messages and
        # processing them.

        while True:
            try:
                message = self.gmail.get_next_message()
            except Exception as error:
                # If an error occurs, wait a while and try again
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
                    text = self._remove_unwanted_characters(text)
                    new_text = []
                    for line in text.split("\n"):
                        line = line.strip()
                        if line != "":
                            new_text.append(line)

                        line = self._shorten_url(line)

                    text = "\n\n".join(new_text)

                    # Messages can be longer than I want on an iMessage, so shorten
                    # it to an appropriate length
                    if (
                        len(text) > self.message_length
                    ):  # Shorten the message to fit into a text
                        text = f"{text[:self.message_length]}\n\n........"

                    message_text = (
                        f"To: {message.to_email}\nSubject: "
                        f"{message.subject}\n\n{text}"
                    )

                    # send the message
                    self.imessage.send_message(message_text)
                    self.logger.info(
                        f"Message sent to {message.to_email}: " f"{message.subject}"
                    )
                except Exception as error:
                    # If an error occurs, sleep for bit to see if it clears up,
                    # but don't bother trying to resend it
                    error_string = f"An error occurred trying to send message:{error}"

                    # self.imessage.send_message(error_string)
                    self.logger.error(error_string)
                    ic(error_string)
                    time.sleep(
                        60 * 10
                    )  # 10 minutes so I don't flood the texts overnight
                    continue

                try:
                    # After we've successfully gotten and (hopefully) sent the
                    # message, delete it
                    self.gmail.delete_message(message.message_id)
                except Exception as error:
                    error_string = f"An error occurred trying to delete message:{error}"

                    self.imessage.send_message(error_string)
                    self.logger.error(error_string)
                    ic(error_string)

            time.sleep(10)

    def _remove_unwanted_characters(self, line: str) -> str:
        for unicode_char in ["\u200c", "&#847;", "&zwnj;", "&nbsp;"]:
            text = text.replace(unicode_char, "")
        return text

    def _shorten_url(self, line: str) -> str:
        # Do the URL shortening
        match_result = http_match.match(line)
        if match_result is not None:
            results = []
            if match_result.group(0) != "":
                results.append(match_result.group(1))
            results.append(match_result.group(2))
            if match_result.group(3) != "":
                results.append(match_result.group(3))
            line = "".join(results)
        return line
