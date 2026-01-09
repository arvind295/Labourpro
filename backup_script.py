import os
import json
import pandas as pd
from datetime import datetime
from supabase import create_client

# 1. SETUP CONNECTION
# We use os.environ to get secrets from GitHub Actions later
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Error: Secrets not found.")
    exit()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def fetch_data(table):
    all_data = []
    page_size = 1000
    current_start = 0
    while True:
        try:
            response = supabase.table(table).select("*").range(current_start, current_start + page_size - 1).execute()
            data_chunk = response.data
            all_data.extend(data_chunk)
            if len(data_chunk) < page_size: break
            current_start += page_size
        except Exception as e:
            print(f"Error fetching {table}: {e}")
            break
    return all_data

# 2. FETCH DATA
print("⏳ Fetching data...")
tables = ["entries", "users", "sites", "contractors"]
backup_data = {}

for t in tables:
    backup_data[t] = fetch_data(t)

# 3. CONVERT TO JSON
json_data = json.dumps(backup_data, default=str)
date_str = datetime.now().strftime("%Y-%m-%d")
file_name = f"backup_{date_str}.json"

# 4. UPLOAD TO SUPABASE STORAGE
print(f"🚀 Uploading {file_name} to Storage...")
try:
    # Convert string to bytes for upload
    file_bytes = json_data.encode('utf-8')
    
    # Upload to 'daily_backups' bucket
    supabase.storage.from_("daily_backups").upload(
        file=file_bytes, 
        path=file_name, 
        file_options={"content-type": "application/json"}
    )
    print("✅ Backup Successful!")
except Exception as e:
    print(f"❌ Upload Failed: {e}")
    # If file exists, update it
    if "The resource already exists" in str(e):
        supabase.storage.from_("daily_backups").update(
            file=file_bytes, 
            path=file_name, 
            file_options={"content-type": "application/json"}
        )
        print("✅ Backup Updated Successfully!")