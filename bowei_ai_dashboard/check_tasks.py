import sqlite3
c = sqlite3.connect('bowei_ai_dashboard.db')

# tasks table
print("--- tasks columns ---")
for row in c.execute("PRAGMA table_info(tasks)"):
    print(row)

print("\n--- Tasks in project 1 ---")
for row in c.execute("SELECT id, name, status FROM tasks WHERE project_id=1"):
    print(f"  {row}")

# subtasks 
print("\n--- subtasks columns ---")
for row in c.execute("PRAGMA table_info(subtasks)"):
    print(row)

print("\n--- Subtasks in project 1 ---")
for row in c.execute("SELECT id, description, status, assignee_person_id FROM subtasks WHERE project_id=1"):
    print(f"  {row}")

c.close()
