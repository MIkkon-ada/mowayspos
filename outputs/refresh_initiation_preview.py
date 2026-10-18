"""Refresh only the previously identified disposable local preview backend."""
from pathlib import Path
import importlib.util
import json
import os
import psutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime
from urllib.parse import unquote, urlsplit

root = Path(__file__).resolve().parents[1]
backend = root / 'bowei_ai_dashboard'
runtime_file = root / 'outputs/initiation-preview-runtime.json'
runtime = json.loads(runtime_file.read_text(encoding='utf-8')) if runtime_file.exists() else {}
process = psutil.Process(runtime.get('pid', 17148))
environment = process.environ()
database = Path(unquote(urlsplit(environment['DATABASE_URL']).path).lstrip('/')).resolve()
expected = (Path(tempfile.gettempdir()) / 'mowayspos-preview-fixed' / 'preview.sqlite').resolve()
assert environment.get('APP_ENV') == 'test' and database == expected, 'Preview target changed; refusing migration/restart'
backup = database.with_name('before-initiation-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '.sqlite')
with sqlite3.connect(database) as source, sqlite3.connect(backup) as target:
    source.backup(target)

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
engine = sa.create_engine(environment['DATABASE_URL'])
columns = {column['name'] for column in sa.inspect(engine).get_columns('projects')}
if 'owner_plan_drafts' not in columns:
    spec = importlib.util.spec_from_file_location('draft_migration', backend / 'migrations/versions/y6z7a8b9c0d1_add_owner_plan_drafts.py')
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
        migration.upgrade()
engine.dispose()
process.terminate()
process.wait(timeout=15)
log = (root / 'outputs/initiation-preview-backend.log').open('ab')
new_process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8011'],
    cwd=backend, env=environment, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
result = {'pid': new_process.pid, 'database': str(database), 'backup': str(backup), 'environment': 'test'}
(root / 'outputs/initiation-preview-runtime.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False))
