import sqlite3

def check_db():
    try:
        conn = sqlite3.connect('migrateiq.db')
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='table_comparison'")
        if not cursor.fetchone():
            print("Table 'table_comparison' does not exist.")
            return

        print("--- RECENT DATABASE ENTRIES ---")
        query = """
            SELECT id, table_name, row_count_twbx, row_count_pbix, result, match_method 
            FROM table_comparison 
            ORDER BY id DESC 
            LIMIT 15
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        
        if not rows:
            print("No records found in table_comparison.")
            return

        for row in rows:
            print(f"ID: {row[0]} | Table: {row[1]:<30} | TWBX: {str(row[2]):>6} | PBIX: {str(row[3]):>6} | Res: {row[4]:<5} | Method: {row[5]}")
        
    except Exception as e:
        print(f"Error checking DB: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    check_db()
