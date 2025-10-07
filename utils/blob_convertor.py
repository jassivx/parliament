import mysql.connector
import hashlib
import os
from config.db_config import db_config

def file_to_blob(file_path: str) -> bytes:
    """Convert file into binary data (BLOB)."""
    try:
        with open(file_path, "rb") as file:
            return file.read()
    except Exception as e:
        print(f"❌ Error converting file to blob: {e}")
        return None

def blob_to_file(blob_data: bytes, output_path: str):
    """Save BLOB binary data back to a file."""
    try:
        with open(output_path, "wb") as file:
            file.write(blob_data)
        print(f"✅ File saved at {output_path}")
    except Exception as e:
        print(f"❌ Error writing blob to file: {e}")

def compute_file_hash(file_path: str) -> str:
    """Compute SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    except Exception as e:
        print(f"❌ Error computing hash for {file_path}: {e}")
        return None

def save_file_to_db(file_path: str):
    """Save a file as BLOB in MySQL (blob_data table). Avoid duplicates using file_hash."""
    blob_data = file_to_blob(file_path)
    if blob_data is None:
        return None

    file_hash = compute_file_hash(file_path)
    if not file_hash:
        return None

    try:
        conn = mysql.connector.connect(**db_config, database="parliament_data")
        cursor = conn.cursor()

        # 🔍 Step 1: Check if file already exists
        cursor.execute("SELECT id FROM blob_data WHERE file_hash = %s", (file_hash,))
        existing = cursor.fetchone()

        if existing:
            print(f"⚠️ File {file_path} already exists in DB with id={existing[0]}")
            cursor.close()
            conn.close()
            return existing[0]

        # 🆕 Step 2: Insert new file
        query = "INSERT INTO blob_data (file_name, file_data, file_hash) VALUES (%s, %s, %s)"
        cursor.execute(query, (os.path.basename(file_path), blob_data, file_hash))
        conn.commit()

        inserted_id = cursor.lastrowid
        print(f"✅ File {file_path} saved as BLOB with id={inserted_id}")

        cursor.close()
        conn.close()
        return inserted_id

    except mysql.connector.Error as err:
        print(f"❌ MySQL error: {err}")
        return None

def fetch_file_from_db(file_id: int, output_path: str):
    """Fetch BLOB from DB and save as file."""
    try:
        conn = mysql.connector.connect(**db_config, database="parliament_data")
        cursor = conn.cursor()

        cursor.execute("SELECT file_data FROM blob_data WHERE id = %s", (file_id,))
        result = cursor.fetchone()

        if result and result[0]:
            blob_to_file(result[0], output_path)
        else:
            print(f"⚠️ No file found with id={file_id}")

        cursor.close()
        conn.close()
    except mysql.connector.Error as err:
        print(f"❌ MySQL error: {err}")

# 🔽 MAIN ENTRY POINT 🔽
if __name__ == "__main__":
    folder_path = "C:/Users/HP/Documents/Scanned Documents/doc"

    if not os.path.exists(folder_path):
        print(f"❌ Folder {folder_path} does not exist!")
    else:
        print(f"📂 Reading files from {folder_path} ...")
        for file_name in os.listdir(folder_path):
            file_path = os.path.join(folder_path, file_name)

            # only process PDFs (change/add more extensions if needed)
            if file_name.lower().endswith(".pdf"):
                save_file_to_db(file_path)
