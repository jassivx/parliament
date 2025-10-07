import mysql.connector
from config.db_config import db_config

def fetch_all_metadata():
    """Fetch all rows from metadata table."""
    try:
        conn = mysql.connector.connect(**db_config, database="parliament_data")
        cursor = conn.cursor(dictionary=True)

        # ✅ Fetch everything from metadata (which references blob_data.id as file_id)
        cursor.execute("SELECT * FROM metadata")
        rows = cursor.fetchall()

        cursor.close()
        conn.close()
        return rows
    except mysql.connector.Error as err:
        print(f"❌ MySQL error: {err}")
        return []

def fetch_text_by_file_id(file_id: int):
    """Fetch extracted text for a given file_id (links to blob_data.id)."""
    try:
        conn = mysql.connector.connect(**db_config, database="parliament_data")
        cursor = conn.cursor()

        # ✅ extracted_text.file_id refers to blob_data.id
        cursor.execute("SELECT content FROM extracted_text WHERE file_id = %s", (file_id,))
        result = cursor.fetchone()

        cursor.close()
        conn.close()
        return result[0] if result else None
    except mysql.connector.Error as err:
        print(f"❌ MySQL error: {err}")
        return None

# ✅ Standalone testing
if __name__ == "__main__":
    print("📋 Fetching all metadata...")
    rows = fetch_all_metadata()
    for r in rows:
        print(r)

    if rows:
        print("\n📄 Fetching text for first file_id...")
        # ✅ metadata table already has file_id column that maps to blob_data.id
        text = fetch_text_by_file_id(rows[0]["file_id"])
        print(text[:500] + "..." if text else "No text found")
