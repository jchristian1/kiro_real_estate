"""
Verificar el contenido de test_config.db antes de eliminarla.
"""

import sqlite3
import os

db_file = 'test_config.db'

if not os.path.exists(db_file):
    print(f"❌ {db_file} no existe")
    exit()

print(f"📊 Analizando {db_file}...")
print(f"Tamaño: {os.path.getsize(db_file)} bytes")

try:
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # Ver tablas
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print(f"\nTablas encontradas ({len(tables)}):")
    for table in tables:
        print(f"  - {table[0]}")
    
    # Ver usuarios si existe la tabla
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    if cursor.fetchone():
        cursor.execute("SELECT id, username, role FROM users")
        users = cursor.fetchall()
        print(f"\nUsuarios en {db_file}:")
        for user in users:
            print(f"  - ID: {user[0]}, Username: {user[1]}, Role: {user[2]}")
    else:
        print(f"\nNo hay tabla 'users' en {db_file}")
    
    # Verificar si es la misma base de datos que gmail_lead_sync.db
    print(f"\n🔍 Comparando con gmail_lead_sync.db:")
    if os.path.exists('gmail_lead_sync.db'):
        main_db_size = os.path.getsize('gmail_lead_sync.db')
        test_db_size = os.path.getsize(db_file)
        print(f"  gmail_lead_sync.db: {main_db_size} bytes")
        print(f"  test_config.db: {test_db_size} bytes")
        print(f"  ¿Mismo tamaño?: {'Sí' if main_db_size == test_db_size else 'No'}")
    else:
        print("  gmail_lead_sync.db no encontrado")
    
    conn.close()
    
except Exception as e:
    print(f"Error analizando {db_file}: {e}")

print("\n" + "="*50)
print("RECOMENDACIÓN:")
print("1. Si test_config.db es una copia de prueba o está vacía: ELIMINAR")
print("2. Si tiene datos importantes: HACER BACKUP primero")
print("3. Si es idéntica a gmail_lead_sync.db: ELIMINAR (es redundante)")
print("="*50)