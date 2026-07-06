import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

st.title("🚀 Leveling Dashboard")

scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_file(
    "credentials.json",
    scopes=scopes
)

client = gspread.authorize(creds)

spreadsheet = client.open_by_url(
    "https://docs.google.com/spreadsheets/d/1IlH8DKJ02yWh40ww9xFf3RlZ5dMOFMF8OHwDzWwplGs/edit?gid=508368498#gid=508368498"
)

worksheet = spreadsheet.worksheet(
    "LEVELING_REQUESTS"
)

data = worksheet.get_all_values()

st.write("Filas encontradas:", len(data))

df = pd.DataFrame(
    data[1:],
    columns=data[0]
)

st.dataframe(df)
