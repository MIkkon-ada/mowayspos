import sqlite3, bcrypt
conn = sqlite3.connect('bowei_ai_dashboard.db')
# Reset passwords and clear must_change_password
h = bcrypt.hashpw(b'123456', bcrypt.gensalt()).decode()
conn.execute("UPDATE accounts SET password=?, must_change_password=0 WHERE username='yangyufan'", (h,))
conn.execute("UPDATE accounts SET password=?, must_change_password=0 WHERE username='冯海林'", (h,))
conn.commit()
print('yangyufan password reset done')
print('冯海林 password reset done')
conn.close()
