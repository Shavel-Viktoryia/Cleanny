import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Авторизация через Google API
def authenticate_google_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("D:\Cleaner\Cleaner\mypython-427607-38a29feb0dfa.json", scope)
    client = gspread.authorize(creds)
    return client

def get_worksheet(spreadsheet_url, sheet_name):
    client = authenticate_google_sheets()
    spreadsheet = client.open_by_url(spreadsheet_url)
    worksheet = spreadsheet.worksheet(sheet_name)
    return worksheet
