"""
Script para diagnosticar problemas de conexión desde la perspectiva de la API.
"""

import sys
import os
sys.path.append('.')

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from api.models.web_ui_models import User
import bcrypt

def test_database_connection():
    """Probar la conexión a la base de datos usando la misma configuración que la API."""
    
    # La URL de la base de datos desde alembic.ini
    database_url = "sqlite:///gmail_lead_sync.db"
    print(f"Conectando a: {database_url}")
    print(f"Directorio actual: {os.getcwd()}")
    
    # Verificar si el archivo existe
    db_file = "gmail_lead_sync.db"
    if os.path.exists(db_file):
        print(f"✓ Archivo de base de datos encontrado: {os.path.abspath(db_file)}")
        print(f"  Tamaño: {os.path.getsize(db_file)} bytes")
    else:
        print(f"✗ Archivo de base de datos NO encontrado: {os.path.abspath(db_file)}")
        # Buscar en otros lugares
        print("Buscando archivos .db en el directorio actual...")
        for file in os.listdir('.'):
            if file.endswith('.db'):
                print(f"  Encontrado: {file}")
    
    try:
        # Crear engine y sesión
        engine = create_engine(database_url)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Contar usuarios
        user_count = session.query(User).count()
        print(f"\n✓ Conexión exitosa a la base de datos")
        print(f"  Número de usuarios: {user_count}")
        
        # Listar usuarios
        users = session.query(User).all()
        print(f"\nUsuarios en la base de datos:")
        for user in users:
            print(f"  - {user.username} (role: {user.role}, id: {user.id})")
            
            # Verificar contraseña
            test_password = 'agent123' if user.username == 'agent1' else 'admin123' if user.username == 'admin' else None
            if test_password:
                try:
                    # Verificar con bcrypt
                    password_bytes = test_password.encode('utf-8')
                    hash_bytes = user.password_hash.encode('utf-8')
                    is_valid = bcrypt.checkpw(password_bytes, hash_bytes)
                    status = "✓ Válida" if is_valid else "✗ Inválida"
                    print(f"    Contraseña '{test_password}': {status}")
                except Exception as e:
                    print(f"    Error verificando contraseña: {e}")
        
        session.close()
        return True
        
    except Exception as e:
        print(f"\n✗ Error conectando a la base de datos: {e}")
        return False

def test_authentication_logic():
    """Probar la lógica de autenticación directamente."""
    print("\n" + "="*60)
    print("Probando lógica de autenticación...")
    
    try:
        from api.auth import authenticate_user, hash_password, verify_password
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        
        database_url = "sqlite:///gmail_lead_sync.db"
        engine = create_engine(database_url)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Probar con agent1
        print("\nProbando autenticación para 'agent1':")
        user = session.query(User).filter(User.username == 'agent1').first()
        
        if user:
            print(f"  Usuario encontrado: {user.username} (role: {user.role})")
            print(f"  Hash de contraseña: {user.password_hash[:50]}...")
            
            # Probar verify_password directamente
            test_password = 'agent123'
            try:
                is_valid = verify_password(test_password, user.password_hash)
                print(f"  verify_password('{test_password}', hash): {is_valid}")
                
                if not is_valid:
                    print(f"  ✗ La contraseña no coincide con el hash")
                    print(f"  ¿Hash generado con diferentes parámetros?")
                    
                    # Generar un nuevo hash para comparar
                    new_hash = hash_password(test_password)
                    print(f"  Nuevo hash para '{test_password}': {new_hash[:50]}...")
                    print(f"  ¿Coincide con el hash almacenado?: {new_hash == user.password_hash}")
                    
            except Exception as e:
                print(f"  Error en verify_password: {e}")
        else:
            print("  ✗ Usuario 'agent1' no encontrado")
        
        session.close()
        
    except ImportError as e:
        print(f"  Error importando módulos: {e}")
    except Exception as e:
        print(f"  Error: {e}")

if __name__ == "__main__":
    print("="*60)
    print("DIAGNÓSTICO DE CONEXIÓN A LA BASE DE DATOS")
    print("="*60)
    
    test_database_connection()
    test_authentication_logic()
    
    print("\n" + "="*60)
    print("RECOMENDACIONES:")
    print("1. Verifica que la API esté usando la misma base de datos")
    print("2. Verifica la ruta de la base de datos en la configuración de la API")
    print("3. Intenta recrear el usuario agent1 con una contraseña nueva")
    print("4. Verifica los logs de la API para más detalles")
    print("="*60)