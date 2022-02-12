import base64
import os.path
import pickle
import traceback
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def get_creds():
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)
    return creds


def send_email(subject, message_text):
    mimetext = MIMEText(message_text)
    mimetext["to"] = "anthony@yesrobo.net"
    mimetext["from"] = "anthonystimetracker@gmail.com"
    mimetext["subject"] = subject
    encoded_message = base64.urlsafe_b64encode(mimetext.as_bytes())
    message_obj = {"raw": encoded_message.decode()}

    try:
        service = build("gmail", "v1", credentials=get_creds())
        message = (
            service.users().messages().send(userId="me", body=message_obj).execute()
        )
        print("Sent Gmail Message Id: {}".format(message["id"]))
    except Exception as error:
        print(f"While sending Gmail message, an error occurred: {error}")
        traceback.print_exc()
