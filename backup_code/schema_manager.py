import mysql.connector
from config.db_config import db_config
from database.connection import DatabaseConnection


class SchemaManager:
    def __init__(self):
        self.db_config = db_config

    def create_parliament_database(self):
        """Create database parliament_data if not exists"""
        conn = None
        cursor = None
        try:
            conn = mysql.connector.connect(**self.db_config)  # connect without DB
            cursor = conn.cursor()
            cursor.execute("SHOW DATABASES LIKE 'parliament_data'")
            result = cursor.fetchone()

            if result:
                print("📂 Database 'parliament_data' already exists.")
            else:
                cursor.execute(
                    "CREATE DATABASE parliament_data CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
                print("🎉 Database 'parliament_data' created successfully!")

        except mysql.connector.Error as err:
            print(f"❌ Failed to create database: {err}")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def create_required_tables(self):
        """Ensure required tables exist in parliament_data"""
        conn = None
        cursor = None
        try:
            conn = DatabaseConnection(with_database=True).connect()
            if conn is None:
                return False

            cursor = conn.cursor()

            tables = {
                "blob_data": """
                    CREATE TABLE IF NOT EXISTS blob_data (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        file_name VARCHAR(255),
                        file_data LONGBLOB,
                        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """,
                "extracted_text": """
                    CREATE TABLE IF NOT EXISTS extracted_text (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        file_id INT,
                        content LONGTEXT,
                        FOREIGN KEY (file_id) REFERENCES blob_data(id) ON DELETE CASCADE
                    )
                """,
                "metadata": """
                    CREATE TABLE IF NOT EXISTS metadata (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        file_id INT,
                        s_no VARCHAR(50),
                        department VARCHAR(255),
                        mp_name VARCHAR(255),
                        answered_on DATE,
                        subject VARCHAR(500),
                        doc_type VARCHAR(100),
                        issuing_person VARCHAR(255),
                        place VARCHAR(255),
                        date DATE,
                        FOREIGN KEY (file_id) REFERENCES blob_data(id) ON DELETE CASCADE
                    )
                """
            }

            for name, ddl in tables.items():
                cursor.execute(ddl)
                print(f"✅ Table '{name}' is ready.")

            conn.commit()
            return True

        except mysql.connector.Error as err:
            print(f"❌ Error while creating tables: {err}")
            return False

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()


# ✅ Run independently for testing
if __name__ == "__main__":
    schema = SchemaManager()
    schema.create_parliament_database()
    schema.create_required_tables()
