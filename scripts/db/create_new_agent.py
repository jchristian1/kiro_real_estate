"""
Crear un nuevo usuario agente con contraseña simple para pruebas.
"""

import bcrypt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from api.models.web_ui_models import User
from datetime import datetime

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    password_bytes = password.encode('utf-8')
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')

# Conexión a la base de datos
engine = create_engine('sqlite:///./gmail_lead_sync.db')
Session = sessionmaker(bind=engine)
session = Session()

# Crear un nuevo usuario agente con contraseña simple
new_username = 'testagent'
new_password = 'test123'

# Verificar si ya existe
existing_user = session.query(User).filter(User.username == new_username).first()
if existing_user:
    print(f"⚠️ Usuario '{new_username}' ya existe. Eliminando...")
    session.delete(existing_user)
    session.commit()

# Crear nuevo usuario
password_hash = hash_password(new_password)
new_user = User(
    username=new_username,
    password_hash=password_hash,
    role='agent',
    created_at=datetime.utcnow()
)

session.add(new_user)
session.commit()

print(f"✅ Nuevo usuario creado:")
print(f"   Username: {new_username}")
print(f"   Password: {new_password}")
print(f"   Role: agent")
print(f"   Hash: {password_hash[:50]}...")

# Verificar que funciona
test_password = new_password
password_bytes = test_password.encode('utf-8')
hash_bytes = password_hash.encode('utf-8')
is_valid = bcrypt.checkpw(password_bytes, hash_bytes)
print(f"   Verificación: {'✅ Válida' if is_valid else '❌ Inválida'}")

session.close()

print("\n🔍 Ahora prueba iniciar sesión con:")
print(f"   Usuario: {new_username}")
print(f"   Contraseña: {new_password}")
print("\nUsa curl para probar:")
print(f'curl -X POST http://localhost:8000/api/v1/auth/login \\')
print(f'  -H "Content-Type: application/json" \\')
print(f'  -d \'{{"username": "{new_username}", "password": "{new_password}"}}\'')