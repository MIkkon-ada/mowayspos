import sqlite3
c = sqlite3.connect('bowei_ai_dashboard.db')

print("=== TASKS ===")
for row in c.execute("PRAGMA table_info(tasks)"):
    print(row)
print()
for row in c.execute("SELECT * FROM tasks WHERE project_id=1"):
    print(row)

print("\n=== SUBTASKS ===")
for row in c.execute("PRAGMA table_info(subtasks)"):
    print(row)
print()
for row in c.execute("SELECT * FROM subtasks"):
    print(row)

# Check if 杨宇帆 is assigned to any subtask
print("\n=== Subtasks assigned to person 6 ===")
for row in c.execute("SELECT * FROM subtasks WHERE assignee_person_id=6"):
    print(row)

c.close()
