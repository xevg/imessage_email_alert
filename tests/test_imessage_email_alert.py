from imessage_email_alert import iMessageEmailAlert
from pathlib import Path

imessage = iMessageEmailAlert(
    "scripting@schore.org", log_dir=Path("/Users/xev/logs"), debug=True
)
imessage.process_messages()
