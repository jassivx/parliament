# utils/pdf_reader.py
import os
import hashlib
from PyPDF2 import PdfReader
from database.database_connector import DatabaseManager  # or DatabaseConnector

# -------------------------------
# PDF Utilities (Standalone Functions)
# -------------------------------

def list_pdfs(folder_path: str):
    """List all PDF files inside a folder."""
    pdf_files = [f for f in os.listdir(folder_path) if f.lower().endswith(".pdf")]
    return [os.path.join(folder_path, f) for f in pdf_files]

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from a PDF file."""
    try:
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text.strip()
    except Exception as e:
        print(f"❌ Error reading {pdf_path}: {e}")
        return ""

def compute_file_hash(file_path: str) -> str:
    """Compute SHA-256 hash for a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def save_pdf_to_db(pdf_path: str, db: DatabaseManager):
    """Save PDF binary + metadata to DB if not already exists."""
    try:
        file_name = os.path.basename(pdf_path)
        file_hash = compute_file_hash(pdf_path)

        # ✅ Check if hash exists
        query = "SELECT id FROM blob_data WHERE file_hash = %s"
        exists = db.fetch_one(query, (file_hash,))
        if exists:
            print(f"⚠️ Skipping {file_name}, already in DB.")
            return None

        # ✅ Read binary data
        with open(pdf_path, "rb") as f:
            file_data = f.read()

        # ✅ Insert into DB
        insert_query = """
            INSERT INTO blob_data (file_name, file_data, file_hash)
            VALUES (%s, %s, %s)
        """
        db.execute_query(insert_query, (file_name, file_data, file_hash))
        print(f"✅ Saved {file_name} to DB.")
        return True

    except Exception as e:
        print(f"❌ Error saving {pdf_path} to DB: {e}")
        return None

# -------------------------------
# Standalone Testing
# -------------------------------
if __name__ == "__main__":
    from database.database_connector import DatabaseConnector
    from config.db_config import DB_CONFIG

    db = DatabaseConnector(DB_CONFIG)
    folder = "C:/Users/HP/Documents/Scanned Documents/doc"
    files = list_pdfs(folder)
    print("📂 Found PDFs:", files)

    for f in files:
        print(f"\n📄 Processing: {f}")
        text = extract_text_from_pdf(f)
        print("📝 Text Preview:", text[:200], "...")
        save_pdf_to_db(f, db)
