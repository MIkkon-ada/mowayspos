import sqlite3
c = sqlite3.connect('bowei_ai_dashboard.db')
for row in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
    print(row[0])
c.close()
