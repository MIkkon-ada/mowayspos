import sqlite3
from datetime import datetime
c = sqlite3.connect('bowei_ai_dashboard.db')

now = datetime.now().isoformat()
# Add 杨宇帆 as member of project 1 (AI升级计划)
c.execute("""
    INSERT INTO project_members (project_id, person_id, person_name_snapshot, role, joined_at, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
""", (1, 6, '杨宇帆', 'member', now, now, now))
c.commit()
print("Added 杨宇帆 to project 1")

# Verify
for row in c.execute("""
    SELECT pm.*, p.name as person_name, pr.name as project_name 
    FROM project_members pm 
    JOIN people p ON pm.person_id = p.id 
    JOIN projects pr ON pm.project_id = pr.id
    WHERE p.name='杨宇帆'
"""):
    print(f"  Success: {row[-1]} - role={row[4]}")

c.close()
