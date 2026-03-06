"""
Script para crear un usuario agente para probar la funcionalidad.
"""

import bcrypt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from api.models.web_ui_models import User
from gmail_lead_sync.models import Base
from datetime import datetime

# Conexión a la BD
engine = create_engine('sqlite:///./gmail_lead_sync.db')

# Crear todas las tablas si no existen
Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)
session = Session()

def hash_password(password: str) -> str:
    """Hash a password using bcrypt with automatic salt generation."""
    salt = bcrypt.gensalt()
    password_bytes = password.encode('utf-8')
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')

# Verificar si ya existe un usuario agente
existing_agent = session.query(User).filter(User.username == 'agent1').first()
if existing_agent:
    print('✓ Usuario agente ya existe:')
    print(f'  Username: {existing_agent.username}')
    print(f'  Role: {existing_agent.role}')
else:
    # Crear usuario agente
    password = 'agent123'  # Contraseña simple para pruebas
    password_hash = hash_password(password)
    
    agent_user = User(
        username='agent1',
        password_hash=password_hash,
        role='agent',
        created_at=datetime.utcnow()
    )
    
    session.add(agent_user)
    session.commit()
    print('✓ Usuario agente creado exitosamente')
    print('  Username: agent1')
    print('  Password: agent123')
    print('  Role: agent')

# También crear un segundo agente por si acaso
existing_agent2 = session.query(User).filter(User.username == 'agent2').first()
if existing_agent2:
    print(f'✓ Usuario agent2 ya existe (Role: {existing_agent2.role})')
else:
    password = 'agent123'
    password_hash = hash_password(password)
    
    agent_user2 = User(
        username='agent2',
        password_hash=password_hash,
        role='agent',
        created_at=datetime.utcnow()
    )
    
    session.add(agent_user2)
    session.commit()
    print('✓ Usuario agent2 creado exitosamente')
    print('  Username: agent2')
    print('  Password: agent123')
    print('  Role: agent')

# Listar todos los usuarios
print('\n📋 Usuarios en la base de datos:')
users = session.query(User).all()
for user in users:
    print(f'  - {user.username} (Role: {user.role})')

session.close()