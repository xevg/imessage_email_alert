import os
import sys
import subprocess


class SendImessage:
    """
    Using applescript on a local machine running messages, send a message
    """

    def __init__(self, buddy: str) -> None:
        """
        Buddy can be either a phone number with countrycode (eg +12125551212) or an
        email address registered with iMessage
        """

        self.buddy = buddy
        self.applescript_file = os.path.join(
            os.path.dirname(sys.modules[__name__].__file__), "messageTexter.applescript"
        )

    def send_message(self, message: str) -> None:
        """
        This is the component that sends the message using applescript
        """

        subprocess.run(
            [
                "osascript",
                self.applescript_file,
                self.buddy,
                message,
            ]
        )
