from __future__ import print_function

import base64
import email
import sys
import os.path
import subprocess
import time
import logging
from pathlib import Path
from bs4 import BeautifulSoup
from html.parser import HTMLParser

import google.auth.exceptions
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://mail.google.com/"]
phone_number = "scripting@schore.org"
message_length = 1000

logfile_dir = Path.home() / "logs"
app_name = "EmailMonitoring"
log_format: str = "%(asctime)s [%(process)d] <%(name)s> %(message)s"
date_format: str = "%Y-%m-%d %I:%M:%S %p"
logger = logging.getLogger(app_name)
logger.setLevel(logging.INFO)
logging.Formatter(log_format, datefmt=date_format)

file_handler = logging.FileHandler(f"{str(Path(logfile_dir) / app_name)}.log", mode="a")
file_handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))
logger.addHandler(file_handler)

stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))
logger.addHandler(stdout_handler)

logger.info("Starting Email Alert Service")


class DeleteError(Exception):
    pass


class HTMLFilter(HTMLParser):
    text = ""

    def handle_data(self, data):
        self.text += data


def send_message(message: str) -> None:
    """
    This is the component that sends the message using applescript
    """

    subprocess.run(
        [
            "osascript",
            "messageTexter.applescript",
            phone_number,
            message,
        ]
    )


def authorize(credentials_file_path: Path, token_file_path: Path) -> Credentials:
    """Shows basic usage of authorization"""
    credentials = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(token_file_path):
        try:
            credentials = Credentials.from_authorized_user_file(
                str(token_file_path), SCOPES
            )
            credentials.refresh(Request())
        except google.auth.exceptions.RefreshError as error:
            # if refresh token fails, reset creds to none.
            credentials = None
            print(f"An refresh authorization error occurred: {error}")
    # If there are no (valid) credentials available, let the user log in.
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_file_path), SCOPES
            )
            credentials = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(token_file_path, "w") as token:
            token.write(credentials.to_json())

    return credentials


def get_message(credentials: Credentials, message_id: str):
    # get a message
    service = build("gmail", "v1", credentials=credentials)

    # Call the Gmail v1 API, retrieve message data.
    message = (
        service.users()
        .messages()
        .get(userId="me", id=message_id, format="raw")
        .execute()
    )

    # Parse the raw message.
    mime_msg = email.message_from_bytes(base64.urlsafe_b64decode(message["raw"]))

    from_email = mime_msg["from"]
    to_email = mime_msg["to"]
    subject = mime_msg["subject"]

    # Find full message body
    message_main_type = mime_msg.get_content_maintype()
    text = "Unreadable message"
    html_text = "Unreadable message"
    if message_main_type == "multipart":
        for part in mime_msg.get_payload():
            if part.get_content_type() == "multipart/alternative":
                sub_message = part.get_payload()
                for sub_part in sub_message:
                    if sub_part.get_content_type() == "text/plain":
                        text = sub_part.get_payload()

            if part.get_content_type() == "text/plain":
                text = part.get_payload()

            if part.get_content_type() == "text/html":
                html = part.get_payload()
                # soup = BeautifulSoup(html, "html.parser")
                f = HTMLFilter()
                f.feed(html)
                # html_text = soup.get_text()
                html_text = f.text
                # print(text)
    elif message_main_type == "text":
        # print(mime_msg.get_payload())
        text: str = mime_msg.get_payload()
        if text.startswith("<!DOCTYPE"):
            soup = BeautifulSoup(text, "html.parser")
            text = soup.get_text()

    if text == "Unreadable message" and html_text != "Unreadable message":
        text = html_text

    return from_email, to_email, subject, text


def process_messages(credentials: Credentials):
    # create a gmail service object
    service = build("gmail", "v1", credentials=credentials)

    # Get the list of messages
    results = service.users().messages().list(userId="me").execute()
    messages = results.get("messages", [])

    if not messages:
        return

    for message in messages:
        from_email, to_email, subject, text = get_message(credentials, message["id"])

        # Massage message to the format I want
        text = text.replace("\r\n", "\n")
        while "\n\n" in text:  # Get rid of multiple carriage returns
            text = text.replace("\n\n", "\n")
        text = text.replace("\n", "\n\n")

        message_text = f"To: {to_email}\nSubject: {subject}\n\n{text}"

        if len(message_text) > message_length:  # Shorten the message to fit into a text
            message_text = f"{message_text[:message_length]}\n\n........"
        send_message(message_text)
        logger.info(f"Message sent to {to_email}: {subject}")

        results = (
            service.users().messages().delete(userId="me", id=message["id"]).execute()
        )
        if results != "":
            raise DeleteError(f"Message could not be deleted: {results}")


while True:
    try:
        config_directory = Path.home() / ".config" / "email_alert"
        creds = authorize(
            config_directory / "credentials.json", config_directory / "token.json"
        )
        break
    except Exception as error:
        send_message(f"An error occurred with authorization: {error}")
        logger.error(f"An error occurred with authorization: {error}")
        time.sleep(60 * 10)  # 10 minutes so I don't flood the texts overnight

while True:
    try:
        process_messages(creds)
        time.sleep(5)
    except Exception as error:
        send_message(f"An error occurred trying to get mail: {error}")
        logger.error(f"An error occurred trying to get mail: {error}")
        time.sleep(60 * 10)  # 10 minutes so I don't flood the texts overnight
