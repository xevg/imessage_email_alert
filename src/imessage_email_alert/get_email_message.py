import base64
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import google.auth.exceptions
from bs4 import BeautifulSoup
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


@dataclass
class EmailMessage:
    """Data class to represent an email message"""

    from_email: str = field(default_factory=str)
    to_email: str = field(default_factory=str)
    subject: str = field(default_factory=str)
    body: str = field(default_factory=str)
    message_id: str = field(default_factory=str)


class DeleteError(Exception):
    """Custom exception for when an error occurs deleting a message"""

    def __init__(
        self, message_id: str, message: str = "Failed to delete email message"
    ):
        self.message_id = message_id
        self.message = message

        super().__init__(self.message)


class GetEmailMessage:
    """
    Retrieve email message from gmail
    https://developers.google.com/drive/api/quickstart/python will provide
    information on how to create your credentials

    """

    # If modifying these scopes, delete the file token.json.
    SCOPES: list = ["https://mail.google.com/"]
    config_directory: Path = Path.home() / ".config" / "imessage_email_alert"

    def __init__(self, credential_file: Path = None, token_file: Path = None):
        """
        Optionally pass in paths to the credentials file and the token file.
        By default, they live in ~/.config/imessage_email_alert as
        .credentials.json and .token.json
        """
        if credential_file is None:
            self.credential_file = self.config_directory / ".credentials.json"
        else:
            self.credential_file = credential_file

        if token_file is None:
            self.token_file = self.config_directory / ".token.json"
        else:
            self.token_file = token_file

        self.credentials = self._authorize()

    def get_next_message(self) -> Optional[EmailMessage]:
        """
        Retrieve the next email message
        """
        # create a gmail service object
        service = build("gmail", "v1", credentials=self.credentials)

        # Get the list of messages
        results = service.users().messages().list(userId="me").execute()
        messages = results.get("messages", [])

        if not messages:
            # If there are no messages available, just return
            return

        message_id = messages[0]["id"]

        result = EmailMessage(message_id=message_id)
        message = (
            service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )
        message_id: str = message["id"]
        payload: dict = message["payload"]
        header_list: list = payload["headers"]
        mime_type = payload["mimeType"]

        headers = self._convert_name_value_list(header_list)
        result.from_email = headers.get("From")
        result.to_email = headers.get("To")
        result.subject = headers.get("Subject")

        # This next section is responsible for decoding the message, be it plain
        # text, or html.

        message_main_type = mime_type.split("/")[0]

        text = "Unreadable message"
        html_text = "Unreadable message"

        parts = payload.get("parts")
        if parts:
            text, html_text = self._parse_parts(parts)
        else:
            decoded_data = base64.urlsafe_b64decode(payload["body"]["data"]).decode(
                "utf-8"
            )
            mime_type = payload["mimeType"]
            match mime_type:
                case "text/plain":
                    text = decoded_data

                case "text/html":
                    soup = BeautifulSoup(decoded_data, "html.parser")
                    html_text = soup.get_text()

                case "text":
                    text = decoded_data
                    if decoded_data.startswith("<!DOCTYPE"):
                        soup = BeautifulSoup(decoded_data, "html.parser")
                        text = soup.get_text()
            pass
        if text == "Unreadable message" and html_text != "Unreadable message":
            text = html_text

        result.body = text
        return result

    def _parse_parts(self, parts: list) -> (str, str):
        text = "Unreadable message"
        html_text = "Unreadable message"

        for part in parts:  # type: dict
            sub_part = part.get("parts")
            if sub_part:
                text, html_text = self._parse_parts(sub_part)
            else:
                part_mime_type = part.get("mimeType")

                match part_mime_type:
                    case "text/plain":
                        if part["body"].get("date") is not None:
                            if part["body"]["data"] != "Unreadable message":
                                decoded_data = base64.urlsafe_b64decode(
                                    part["body"]["data"]
                                ).decode("utf-8")
                                text = decoded_data

                    case "text/html":
                        if part["body"].get("date") is not None:
                            if part["body"]["data"] != "Unreadable message":
                                decoded_data = base64.urlsafe_b64decode(
                                    part["body"]["data"]
                                ).decode("utf-8")
                                soup = BeautifulSoup(decoded_data, "html.parser")
                                html_text = soup.get_text()

                    case "text":
                        if part["body"].get("date") is not None:
                            if part["body"]["data"] != "Unreadable message":
                                decoded_data = base64.urlsafe_b64decode(
                                    part["body"]["data"]
                                ).decode("utf-8")
                                text = decoded_data
                                if decoded_data.startswith("<!DOCTYPE"):
                                    soup = BeautifulSoup(decoded_data, "html.parser")
                                    text = soup.get_text()
                pass
        return text, html_text

    def delete_message(self, message_id: str):
        service = build("gmail", "v1", credentials=self.credentials)

        results = (
            service.users().messages().delete(userId="me", id=message_id).execute()
        )
        if results != "":
            raise DeleteError(message_id, f"Message could not be deleted: {results}")

    @staticmethod
    def _convert_name_value_list(name_value_list: list) -> dict:
        result = {}
        for item in name_value_list:
            name = item["name"]
            value = item["value"]
            result[name] = value
        return result

    def _authorize(self) -> Credentials:
        """
        Authorize Google Account, taken from
        https://stackoverflow.com/questions/74487595/read-full-message-in-email-with-gmail-api
        """

        credentials = None
        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists(self.token_file):
            try:
                credentials = Credentials.from_authorized_user_file(
                    str(self.token_file), self.SCOPES
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
                    str(self.credential_file), self.SCOPES
                )
                credentials = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open(self.token_file, "w") as token:
                token.write(credentials.to_json())

        return credentials
