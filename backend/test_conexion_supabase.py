"""
Prueba rápida: ¿la app se puede conectar a Supabase y crear las tablas?

Corré esto desde la carpeta backend/ con el venv activado:
    python test_conexion_supabase.py

Si todo sale bien, vas a ver "TODO OK" al final, y en el dashboard de
Supabase (Table Editor) van a aparecer las tablas nuevas: users,
prendas, outfits, user_profile, virtual_tryons, combo_tryons.
"""

from database import init_db, crear_usuario, obtener_usuario_por_email

print("Conectando a Supabase...")
init_db()
print("✅ Tablas creadas (o ya existían). Revisá el Table Editor en Supabase.")

print("\nProbando crear un usuario de prueba...")
email_prueba = "prueba_conexion@ejemplo.com"

existente = obtener_usuario_por_email(email_prueba)
if existente:
    print(f"✅ El usuario de prueba ya existía (id={existente['id']}). Conexión OK.")
else:
    nuevo_id = crear_usuario(email_prueba, "hash_falso_solo_de_prueba", "Usuario Prueba")
    print(f"✅ Usuario de prueba creado con id={nuevo_id}.")

print("\n🎉 TODO OK — la conexión a Supabase funciona correctamente.")
