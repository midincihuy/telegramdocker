from google.oauth2 import service_account
from googleapiclient.discovery import build
import json

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
creds = service_account.Credentials.from_service_account_file(
        "/credentials/service_account.json",
        scopes=SCOPES,
    )

service = build("sheets", "v4", credentials=creds)

def get_schedule(sheet_id: str):
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range="Schedule!A2:G"
    ).execute()

    rows = result.get("values", [])
    schedules = []

    for row in rows:
        if len(row) < 5:
            continue

        active, hour, minute, interval, day, function, params = row

        if active.upper() != "TRUE":
            continue

        schedules.append({
            "hour": hour,
            "minute": minute,
            "interval": interval.strip(),
            "day": day.strip().lower(),
            "function": function,
            "params": json.loads(params),
        })

    return schedules
