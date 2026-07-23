import sqlite3
c = sqlite3.connect('bowei_ai_dashboard.db')

# Find 杨宇帆 in people
for row in c.execute("SELECT id, name FROM people WHERE name LIKE '%宇帆%'"):
    person_id = row[0]
    name = row[1]
    print(f"Person: id={person_id}, name={name}")

    # Check project assignments
    for prj in c.execute("""
        SELECT DISTINCT p.id, p.name, p.status 
        FROM projects p 
        JOIN project_members pm ON p.id = pm.project_id 
        WHERE pm.person_id=?
    """, (person_id,)):
        print(f"  Project: id={prj[0]}, name={prj[1]}, status={prj[2]}")

# All projects and statuses
print("\n--- All projects ---")
for row in c.execute("SELECT id, name, status FROM projects ORDER BY status"):
    print(f"  {row}")

c.close()
