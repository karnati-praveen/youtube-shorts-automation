import sqlite3, shutil, os, tempfile
from pathlib import Path

db = Path(os.environ["LOCALAPPDATA"]) / "Microsoft" / "Edge" / "User Data" / "Default" / "Network" / "Cookies"
tmp = tempfile.mktemp(suffix=".db")
shutil.copy2(str(db), tmp)
conn = sqlite3.connect(tmp)
rows = conn.execute(
    "SELECT host_key, name, encrypted_value FROM cookies "
    "WHERE host_key LIKE '%.youtube.com' LIMIT 5"
).fetchall()
conn.close()
os.unlink(tmp)
for host, name, val in rows:
    print(f"{host} | {name} | prefix={val[:3]} | len={len(val)}")
