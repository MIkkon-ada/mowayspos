import sqlite3
c = sqlite3.connect('bowei_ai_dashboard.db')
c.row_factory = sqlite3.Row
print("TASKS cols:", [r[1] for r in c.execute("PRAGMA table_info(tasks)")])
for r in c.execute("SELECT * FROM tasks WHERE project_id=1"):
    print("TASK:", list(r))
print("SUBS:", [r[1] for r in c.execute("PRAGMA table_info(subtasks)")])
for r in c.execute("SELECT * FROM subtasks"):
    print("SUB:", list(r))
c.close()
