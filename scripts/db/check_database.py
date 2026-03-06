"""
Script para verificar el estado de la base de datos y los usuarios.
"""

import sqlite3
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker as orm_sessionmaker
import sys

print("=== Verificación de Base de Datos ===")

# Verificar si el archivo de base de datos existe
db_path = "./gmail_lead_sync.db"
print(f"1. Verificando archivo de base de datos: {db_path}")
if os.path.exists(db_path):
    print(f"   ✓ Archivo de base de datos encontrado: {os.path.getsize(db_path)} bytes")
else:
    print(f"   ✗ Archivo de base de datos NO encontrado en: {db_path}")
    # Crear directorio si no existe
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

# Conectar a la base de datos SQLite directamente
try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Verificar tablas existentes
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print(f"\n2. Tablas en la base de datos:")
    for table in tables:
        print(f"   - {table[0]}")
    
    # Verificar tabla de usuarios
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    users_table = cursor.fetchone()
    
    if users_table:
        print(f"\n3. Tabla 'users' encontrada")
        # Ver usuarios
        cursor.execute("SELECT id, username, role FROM users")
        users = cursor.fetchall()
        print(f"   Usuarios encontrados ({len(users)}):")
        for user in users:
            print(f"   - ID: {user[0]}, Username: {user[1]}, Role: {user[2]}")
    else:
        print("\n3. Tabla 'users' NO encontrada")
    
    # Verificar tabla de leads
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='leads'")
    leads_table = cursor.fetchone()
    if leads_table:
        cursor.execute("SELECT COUNT(*) FROM leads")
        lead_count = cursor.fetchone()[0]
        print(f"\n4. Tabla 'leads' encontrada con {lead_count} registros")
        
        # Mostrar algunos leads
        cursor.execute("SELECT id, name, agent_id FROM leads LIMIT 5")
        leads = cursor.fetchall()
        print(f"   Primeros {len(leads)} leads:")
        for lead in leads:
            print(f"   - ID: {lead[0]}, Nombre: {lead[1]}, Agente: {lead[2]}")
    
    conn.close()
    print("\n5. Conexión a la base de datos exitosa")
    
except Exception as e:
    print(f"Error al conectar a la base de datos: {e}")
    print(f"Ruta de búsqueda: {os.path.abspath('.')}")
    print(f"Archivo de BD existe: {os.path.exists(db_path)}")

print("\n" + "="*50)
print("Para solucionar problemas de autenticación:")
print("1. Verifica que la API esté usando la misma base de datos")
print("2. Verifica las credenciales de los usuarios")
print("3. Verifica que el servidor API esté corriendo")
print("4. Verifica los logs de la API para errores")