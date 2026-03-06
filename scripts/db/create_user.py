from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from api.models.web_ui_models import User
from gmail_lead_sync.models import Base
from datetime import datetime

# Conexión a la BD
engine = create_engine('sqlite:///./gmail_lead_sync.db')

# Crear todas las tablas
Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)
session = Session()

# Hash ya generado
password_hash = '$2b$12$fdTpezHjeMUBylfKhFSOLORX7VkenxJ0EQCe8yS2oYGcpl9kv841u'

# Crear usuario
user = User(
    username='admin',
    password_hash=password_hash,
    role='admin',
    created_at=datetime.utcnow()
)

session.add(user)
session.commit()
print('✓ Usuario creado exitosamente')
print('  Username: admin')
print('  Password: admin123')
print('  Role: admin')
session.close()
