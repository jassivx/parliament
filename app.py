
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from database.database_connector import DatabaseManager
from utils.blob_convertor import save_file_to_db
from utils.metadata_extractor import process_blobs_and_save_metadata  # ✅ Correct import
from typing import List
import os
import shutil
import tempfile
import mysql.connector

app = FastAPI(
    title="Parliament Data Microservice",
    description="API for processing PDFs, storing as BLOBs, and extracting metadata + QA pairs.",
    version="1.2"
)

# Enable CORS (for frontend access)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://127.0.0.1:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Temporary folder for uploaded files
UPLOAD_FOLDER = tempfile.mkdtemp()


# ------------------------------------------
# 1️⃣ Upload PDF(s) and store as BLOB in DB
# ------------------------------------------
@app.post("/upload-file/")
async def upload_file(files: List[UploadFile] = File(...)):
    """
    Upload multiple PDF files, convert them into BLOBs, and store in DB.
    Automatically creates database and tables if missing.
    """
    db_manager = DatabaseManager()
    db_manager.create_parliament_database()
    if not db_manager.create_required_tables():
        raise HTTPException(status_code=500, detail="Failed to setup database.")

    uploaded_files = []

    for file in files:
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail=f"File {file.filename} is not a PDF.")

        # Save file temporarily
        file_path = os.path.join(UPLOAD_FOLDER, file.filename)
        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            # Save PDF as BLOB in DB
            file_id = save_file_to_db(file_path)
            if file_id:
                uploaded_files.append({"filename": file.filename, "file_id": file_id})
            else:
                raise HTTPException(status_code=500, detail=f"Failed to store file {file.filename}")
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)

    return {
        "message": "✅ Files uploaded and stored successfully!",
        "uploaded_files": uploaded_files
    }


# ------------------------------------------
# 2️⃣ Extract metadata and QA pairs from PDFs
# ------------------------------------------
@app.get("/extract-metadata/")
async def extract_metadata():
    """
    Extract metadata + QA pairs from all BLOB files and store into respective tables.
    Returns a summary of processed files and QA pair counts.
    """
    try:
        summary = process_blobs_and_save_metadata()  # ✅ returns detailed log summary
        return {
            "message": "✅ Metadata and QA pairs extracted successfully!",
            "summary": summary
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error extracting metadata: {e}")


# ------------------------------------------
# 3️⃣ List all stored PDF files
# ------------------------------------------
@app.get("/list-files/")
async def list_files():
    """
    List all files stored in the blob_data table.
    """
    try:
        from config.db_config import db_config
        conn = mysql.connector.connect(**db_config, database="parliament_data")
        cursor = conn.cursor()
        cursor.execute("SELECT id, file_name FROM blob_data")
        files = cursor.fetchall()
        cursor.close()
        conn.close()

        return {"files": [{"id": f[0], "name": f[1]} for f in files]}
    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=f"Error fetching files: {err}")


# ------------------------------------------
# 4️⃣ Run FastAPI Server
# ------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
