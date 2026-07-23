import sqlite3
c = sqlite3.connect('bowei_ai_dashboard.db')

# Check tasks for project 1
print("--- Tasks in project 1 ---")
for row in c.execute("SELECT id, name, status FROM key_tasks WHERE project_id=1"):
    print(f"  Task: id={row[0]}, name={row[1]}, status={row[2]}")

# Check subtasks
print("\n--- Subtasks in project 1 ---")
for row in c.execute("SELECT s.id, s.description, s.status, s.assignee_person_id, t.name as task_name FROM subtasks s JOIN key_tasks t ON s.key_task_id = t.id WHERE t.project_id=1"):
    print(f"  Subtask: id={row[0]}, desc={row[1]}, status={row[2]}, assignee={row[3]}, task={row[4]}")

# Check if 杨宇帆 is assigned to any subtask
print("\n--- Subtasks assigned to 杨宇帆 (person_id=6) ---")
for row in c.execute("SELECT s.id, s.description, t.name FROM subtasks s JOIN key_tasks t ON s.key_task_id = t.id WHERE s.assignee_person_id=6"):
    print(f"  Subtask: id={row[0]}, desc={row[1]}, task={row[2]}")

c.close()
