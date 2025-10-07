import mysql.connector
from config.db_config import db_config


class DatabaseConnection:
    def __init__(self, with_database=True):
        self.db_config = db_config.copy()
        if with_database:
            self.db_config["database"] = "parliament_data"

    def connect(self):
        """Establish a connection to MySQL."""
        try:
            print("🔌 Connecting to MySQL...")
            conn = mysql.connector.connect(**self.db_config)

            if conn.is_connected():
                print("✅ Successfully connected to MySQL!")
                return conn
            else:
                print("❌ Failed to connect to MySQL!")
                return None

        except mysql.connector.Error as err:
            print(f"⚠️ MySQL connection error: {err}")
            return None


# ✅ Run independently for testing
if __name__ == "__main__":
    db = DatabaseConnection(with_database=False)
    conn = db.connect()
    if conn:
        print("🎉 Connection test successful")
        conn.close()

