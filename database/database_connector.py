import mysql.connector
from mysql.connector import errorcode
from config.db_config import db_config


class DatabaseManager:
    def __init__(self):
        self.db_config = db_config

    def connect(self, with_database=True):
        """Connect to MySQL. If with_database=True, connect to parliament_data DB."""
        try:
            config = self.db_config.copy()
            if with_database:
                config["database"] = "parliament_data"

            print("🔌 Connecting to MySQL...")
            conn = mysql.connector.connect(**config)

            if conn.is_connected():
                print("✅ Successfully connected to MySQL!")
                return conn
            else:
                print("❌ Failed to connect to MySQL!")
                return None

        except mysql.connector.Error as err:
            print(f"⚠️ MySQL connection error: {err}")
            return None

    def create_parliament_database(self):
        """Create database parliament_data if not exists"""
        conn = None
        cursor = None
        try:
            conn = mysql.connector.connect(**self.db_config)  # connect without database
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
            conn = self.connect(with_database=True)
            if conn is None:
                return False

            cursor = conn.cursor()

            # Table definitions
            tables = {
                "blob_data": """
                    CREATE TABLE IF NOT EXISTS blob_data (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        file_name VARCHAR(255),
                        file_data LONGBLOB,
                        file_hash VARCHAR(64) UNIQUE,   
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
                        question_number VARCHAR(50),
                        department VARCHAR(255),
                        mp_name VARCHAR(255),
                        answered_on DATE,
                        subject VARCHAR(500),
                        house VARCHAR(100),
                        issuing_person VARCHAR(255),
                        place VARCHAR(255),
                        date DATE,
                        FOREIGN KEY (file_id) REFERENCES blob_data(id) ON DELETE CASCADE
                    )
                """,

                "qa_pairs": """
                    CREATE TABLE IF NOT EXISTS qa_pairs (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        metadata_id INT,
                        sub_question_label VARCHAR(5),
                        question LONGTEXT,
                        answer LONGTEXT,
                        FOREIGN KEY (metadata_id) REFERENCES metadata(id) ON DELETE CASCADE
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


if __name__ == "__main__":
    db_manager = DatabaseManager()

    # Step 1: Create database if not exists
    db_manager.create_parliament_database()

    # Step 2: Create required tables
    db_manager.create_required_tables()
