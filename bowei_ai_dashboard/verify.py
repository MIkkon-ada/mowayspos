import sqlite3
c = sqlite3.connect('bowei_ai_dashboard.db')

print("=== update_submissions ===")
for row in c.execute("PRAGMA table_info(update_submissions)"):
    print(f"  {row[1]} {row[2]}")

print("\n=== update_submissions data ===")
for row in c.execute("SELECT * FROM update_submissions ORDER BY id"):
    print(f"  {list(row)}")

c.close()
