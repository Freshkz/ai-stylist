import sqlite3

conn = sqlite3.connect("../armario.db")
conn.row_factory = sqlite3.Row

filas = conn.execute(
    "SELECT id, tipo, categoria FROM prendas WHERE tipo LIKE '%rail running%' OR tipo LIKE '%apatilla%'"
).fetchall()

for f in filas:
    print(dict(f))

conn.close()