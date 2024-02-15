# read version from installed package
from importlib.metadata import version
from .send_imessage import SendImessage
from .get_email_message import EmailMessage, GetEmailMessage
from .imessage_email_alert import iMessageEmailAlert
import click
from pathlib import Path

__version__ = version("imessage_email_alert")

"""
Send an iMessage alert every time a message comes in to gmail.
The way I set this up is that for every message that I get im my email that
I care about, I send a copy to dummy gmail account. This program retrieves the
message from the dummy gmail account, sends it via iMessage, and then deletes it.

https://developers.google.com/drive/api/quickstart/python will provide
information on how to create your credentials
"""

config_directory: Path = Path.home() / ".config" / "imessage_email_alert"


@click.command()
@click.argument("buddy")
@click.option(
    "--credentials-file",
    required=False,
    type=click.Path(exists=True),
    default=config_directory / ".credentials.json",
    help="The location of the credentials file",
)
@click.option(
    "--token-file",
    required=False,
    type=click.Path(exists=True),
    default=config_directory / ".token.json",
    help="The location to save the token file file",
)
@click.option(
    "--log-dir",
    required=False,
    type=click.Path(exists=True),
    help="The location to save the log file",
)
@click.option(
    "--debug/--no-debug", default=False, help="Enable debugging to the console"
)
@click.option(
    "--save-messages",
    required=False,
    type=click.Path(
        exists=True,
    ),
    help="Directory to save original email messages to",
)
@click.option(
    "--test-messages",
    required=False,
    type=click.Path(exists=True),
    help="Directory containing previously saved messages to test",
)
def imessage_email_alert(
    buddy, credentials_file, token_file, log_dir, debug, save_messages, test_messages
):
    """Sends an iMessage alert to BUDDY (phone number or email) whenever you get an
    email"""
    if log_dir is not None:
        log_dir = Path(log_dir)

    if save_messages is not None:
        save_messages = Path(save_messages)
        save_messages.mkdir(parents=True, exist_ok=True)
        if not save_messages.is_dir():
            print(f"'{save_messages}' is not a directory")
            exit(1)

    if test_messages is not None:
        test_messages = Path(test_messages)
        if not test_messages.is_dir():
            print(f"'{test_messages}' is not a directory")
            exit(1)

    imessage = iMessageEmailAlert(
        buddy,
        credentials_file=credentials_file,
        token_file=token_file,
        log_dir=log_dir,
        debug=debug,
        save_messages=save_messages,
        test_messages=test_messages,
    )
    if test_messages is not None:
        imessage.test_messages()
    else:
        imessage.process_messages()


if __name__ == "__main__":
    imessage_email_alert()
