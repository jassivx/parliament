from database.database_connector import DatabaseManager
from utils.blob_convertor import save_file_to_db
from backup_code.metadata_extractor import process_blobs_and_save_metadata
import os


def main():
    # Step 1: Initialize DatabaseManager and set up the database
    db_manager = DatabaseManager()
    print("🚀 Starting database setup...")

    # Create the parliament_data database if it doesn't exist
    db_manager.create_parliament_database()

    # Create required tables (blob_data, extracted_text, metadata)
    if db_manager.create_required_tables():
        print("✅ Database and tables are ready!")
    else:
        print("❌ Failed to set up database tables. Exiting...")
        return

    # Step 2: Process PDF files and save them as BLOBs
    folder_path = "C:/Users/HP/Documents/Scanned Documents/doc"
    if not os.path.exists(folder_path):
        print(f"❌ Folder {folder_path} does not exist! Exiting...")
        return

    print(f"📂 Processing PDF files from {folder_path}...")
    for file_name in os.listdir(folder_path):
        if file_name.lower().endswith(".pdf"):
            file_path = os.path.join(folder_path, file_name)
            file_id = save_file_to_db(file_path)
            if file_id:
                print(f"✅ Processed {file_name} (file_id={file_id})")
            else:
                print(f"❌ Failed to process {file_name}")

    # Step 3: Extract metadata from stored BLOBs and save to metadata table
    print("📄 Extracting and saving metadata for all stored files...")
    process_blobs_and_save_metadata()
    print("🎉 All files processed and metadata saved!")


if __name__ == "__main__":
    main()



