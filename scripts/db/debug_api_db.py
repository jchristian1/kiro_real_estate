"""
Script para diagnosticar qué base de datos está usando la API.
"""

import os
import sys

# Agregar el directorio actual al path
sys.path.insert(0, os.path.abspath('.'))

print("="*60)
print("DIAGNÓSTICO DE BASE DE DATOS DE LA API")
print("="*60)

# 1. Verificar variables de entorno
print("\n1. Variables de entorno:")
from dotenv import load_dotenv
load_dotenv('api/.env')

database_url = os.getenv('DATABASE_URL')
print(f"   DATABASE_URL: {database_url}")

# 2. Verificar configuración de la API
print("\n2. Configuración de la API:")
try:
    from api.config import load_config
    config = load_config()
    print(f"   database_url: {config.database_url}")
except Exception as e:
    print(f"   Error cargando config: {e}")

# 3. Verificar qué base de datos usa main.py
print("\n3. Configuración en api/main.py:")
try:
    # Leer el archivo main.py para ver la configuración
    with open('api/main.py', 'r', encoding='utf-8') as f:
        content = f.read()
        # Buscar la línea donde se crea el engine
        for i, line in enumerate(content.split('\n')):
            if 'create_engine' in line or 'DATABASE_URL' in line or 'database_url' in line:
                print(f"   Línea {i+1}: {line.strip()}")
except Exception as e:
    print(f"   Error leyendo main.py: {e}")

# 4. Verificar archivos .db existentes
print("\n4. Archivos .db en el directorio:")
for file in os.listdir('.'):
    if file.endswith('.db'):
        size = os.path.getsize(file)
        print(f"   - {file}: {size} bytes")
        
        # Verificar si tiene tabla users
        import sqlite3
        try:
            conn = sqlite3.connect(file)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            has_users = cursor.fetchone() is not None
            
            if has_users:
                cursor.execute("SELECT COUNT(*) FROM users")
                user_count = cursor.fetchone()[0]
                print(f"     ✓ Tiene tabla 'users' con {user_count} usuarios")
            else:
                print(f"     ✗ NO tiene tabla 'users'")
            
            conn.close()
        except Exception as e:
            print(f"     Error verificando: {e}")

# 5. Probar conexión como lo hace la API
print("\n5. Probando conexión como la API:")
try:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from api.models.web_ui_models import User
    
    # Usar la misma configuración que la API
    from api.config import load_config
    config = load_config()
    
    print(f"   Conectando a: {config.database_url}")
    engine = create_engine(config.database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Intentar contar usuarios
    try:
        user_count = session.query(User).count()
        print(f"   ✓ Conexión exitosa: {user_count} usuarios encontrados")
        
        # Listar usuarios
        users = session.query(User).all()
        for user in users:
            print(f"     - {user.username} (role: {user.role})")
    except Exception as e:
        print(f"   ✗ Error consultando usuarios: {e}")
    
    session.close()
    
except Exception as e:
    print(f"   ✗ Error: {e}")

print("\n" + "="*60)
print("RECOMENDACIÓN:")
print("Si la API está usando una base de datos diferente,")
print("necesitas actualizar la configuración o copiar la base de datos")
print("a la ubicación correcta.")
print("="*60)