import os
import sys
import subprocess


class SendImessage:
    def __init__(self, phone_number: str):
        self.phone_number = phone_number
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
                self.phone_number,
                message,
            ]
        )
