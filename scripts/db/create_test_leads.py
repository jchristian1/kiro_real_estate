"""
Script para crear datos de prueba para la funcionalidad de agentes.
Incluye: compañías, credenciales, lead sources y leads.
"""

import bcrypt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta
import random

# Importar modelos
from gmail_lead_sync.models import Base, Company, Credentials, LeadSource, Lead, Template
from api.models.web_ui_models import User

# Conexión a la BD
engine = create_engine('sqlite:///./gmail_lead_sync.db')
Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)
session = Session()

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    password_bytes = password.encode('utf-8')
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')

print("🚀 Creando datos de prueba para la funcionalidad de agentes...")

# 1. Verificar/Crear usuarios agentes si no existen
print("\n1. Verificando usuarios agentes...")
agent_users = ['agent1', 'agent2']
for username in agent_users:
    user = session.query(User).filter(User.username == username).first()
    if not user:
        password_hash = hash_password('agent123')
        user = User(
            username=username,
            password_hash=password_hash,
            role='agent',
            created_at=datetime.utcnow()
        )
        session.add(user)
        print(f"   ✓ Creado usuario: {username} (agent)")
    else:
        print(f"   ✓ Usuario ya existe: {username} (Role: {user.role})")

session.commit()

# 2. Crear compañía de prueba
print("\n2. Creando compañía de prueba...")
company = session.query(Company).filter(Company.name == 'Inmobiliaria Ejemplo S.A.').first()
if not company:
    company = Company(
        name='Inmobiliaria Ejemplo S.A.',
        phone='+1 234 567 8900',
        email='info@inmobiliaria-ejemplo.com',
        created_at=datetime.utcnow()
    )
    session.add(company)
    session.commit()
    print(f"   ✓ Creada compañía: {company.name} (ID: {company.id})")
else:
    print(f"   ✓ Compañía ya existe: {company.name} (ID: {company.id})")

# 3. Crear credenciales para los agentes (asociadas a la compañía)
print("\n3. Creando credenciales para agentes...")
agents_data = [
    {'agent_id': 'agent1', 'display_name': 'Juan Pérez', 'phone': '+1 234 567 8901'},
    {'agent_id': 'agent2', 'display_name': 'María García', 'phone': '+1 234 567 8902'},
]

for agent_data in agents_data:
    creds = session.query(Credentials).filter(Credentials.agent_id == agent_data['agent_id']).first()
    if not creds:
        # Para pruebas, usamos valores dummy encriptados
        creds = Credentials(
            agent_id=agent_data['agent_id'],
            email_encrypted='dummy-encrypted-email',
            app_password_encrypted='dummy-encrypted-password',
            display_name=agent_data['display_name'],
            phone=agent_data['phone'],
            company_id=company.id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        session.add(creds)
        print(f"   ✓ Creadas credenciales para: {agent_data['display_name']} ({agent_data['agent_id']})")
    else:
        print(f"   ✓ Credenciales ya existen para: {creds.display_name} ({creds.agent_id})")

session.commit()

# 4. Crear template de prueba (necesario para lead sources)
print("\n4. Creando template de prueba...")
template = session.query(Template).filter(Template.name == 'Template de Prueba').first()
if not template:
    template = Template(
        name='Template de Prueba',
        subject='Gracias por su interés en nuestras propiedades',
        body='Estimado {nombre}, gracias por contactarnos. Un agente se comunicará con usted pronto.',
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    session.add(template)
    session.commit()
    print(f"   ✓ Creado template: {template.name} (ID: {template.id})")
else:
    print(f"   ✓ Template ya existe: {template.name} (ID: {template.id})")

# 5. Crear lead sources de prueba
print("\n5. Creando lead sources de prueba...")
lead_sources_data = [
    {
        'sender_email': 'clientes@portalinmobiliario.com',
        'identifier_snippet': 'Consulta desde Portal Inmobiliario',
        'name_regex': r'Nombre:\s*(.+)',
        'phone_regex': r'Teléfono:\s*(.+)'
    },
    {
        'sender_email': 'leads@zonaprop.com',
        'identifier_snippet': 'Interesado desde ZonaProp',
        'name_regex': r'Nombre:\s*(.+)',
        'phone_regex': r'Contacto:\s*(.+)'
    }
]

lead_source_ids = []
for ls_data in lead_sources_data:
    ls = session.query(LeadSource).filter(LeadSource.sender_email == ls_data['sender_email']).first()
    if not ls:
        ls = LeadSource(
            sender_email=ls_data['sender_email'],
            identifier_snippet=ls_data['identifier_snippet'],
            name_regex=ls_data['name_regex'],
            phone_regex=ls_data['phone_regex'],
            template_id=template.id,
            auto_respond_enabled=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        session.add(ls)
        session.commit()
        lead_source_ids.append(ls.id)
        print(f"   ✓ Creado lead source: {ls.sender_email} (ID: {ls.id})")
    else:
        lead_source_ids.append(ls.id)
        print(f"   ✓ Lead source ya existe: {ls.sender_email} (ID: {ls.id})")

# 6. Crear leads de prueba
print("\n6. Creando leads de prueba...")

# Datos de leads de prueba
test_leads = [
    # Leads para agent1
    {
        'name': 'Carlos Rodríguez',
        'phone': '+1 555 123 4567',
        'source_email': 'carlos.rodriguez@email.com',
        'agent_id': 'agent1',
        'response_sent': True,
        'response_status': 'sent',
        'days_ago': 1
    },
    {
        'name': 'Ana Martínez',
        'phone': '+1 555 234 5678',
        'source_email': 'ana.martinez@email.com',
        'agent_id': 'agent1',
        'response_sent': False,
        'response_status': None,
        'days_ago': 2
    },
    {
        'name': 'Roberto Sánchez',
        'phone': '+1 555 345 6789',
        'source_email': 'roberto.sanchez@email.com',
        'agent_id': 'agent1',
        'response_sent': True,
        'response_status': 'failed',
        'days_ago': 3
    },
    {
        'name': 'Laura Fernández',
        'phone': '+1 555 456 7890',
        'source_email': 'laura.fernandez@email.com',
        'agent_id': 'agent1',
        'response_sent': False,
        'response_status': None,
        'days_ago': 4
    },
    # Leads para agent2
    {
        'name': 'Pedro Gómez',
        'phone': '+1 555 567 8901',
        'source_email': 'pedro.gomez@email.com',
        'agent_id': 'agent2',
        'response_sent': True,
        'response_status': 'sent',
        'days_ago': 1
    },
    {
        'name': 'Sofía López',
        'phone': '+1 555 678 9012',
        'source_email': 'sofia.lopez@email.com',
        'agent_id': 'agent2',
        'response_sent': False,
        'response_status': None,
        'days_ago': 2
    },
    {
        'name': 'Diego Ramírez',
        'phone': '+1 555 789 0123',
        'source_email': 'diego.ramirez@email.com',
        'agent_id': 'agent2',
        'response_sent': True,
        'response_status': 'sent',
        'days_ago': 3
    },
    # Leads sin agente asignado
    {
        'name': 'Mónica Vargas',
        'phone': '+1 555 890 1234',
        'source_email': 'monica.vargas@email.com',
        'agent_id': None,
        'response_sent': False,
        'response_status': None,
        'days_ago': 5
    },
    {
        'name': 'Andrés Castro',
        'phone': '+1 555 901 2345',
        'source_email': 'andres.castro@email.com',
        'agent_id': None,
        'response_sent': True,
        'response_status': 'failed',
        'days_ago': 6
    }
]

leads_created = 0
for i, lead_data in enumerate(test_leads):
    # Crear Gmail UID único
    gmail_uid = f'test_lead_{i+1}_{datetime.utcnow().timestamp()}'
    
    # Verificar si ya existe
    existing_lead = session.query(Lead).filter(Lead.gmail_uid == gmail_uid).first()
    if existing_lead:
        print(f"   ⚠️ Lead ya existe: {lead_data['name']}")
        continue
    
    # Calcular fecha de creación
    created_at = datetime.utcnow() - timedelta(days=lead_data['days_ago'])
    
    # Seleccionar lead source aleatorio
    lead_source_id = random.choice(lead_source_ids)
    
    # Crear lead
    lead = Lead(
        name=lead_data['name'],
        phone=lead_data['phone'],
        source_email=lead_data['source_email'],
        lead_source_id=lead_source_id,
        gmail_uid=gmail_uid,
        created_at=created_at,
        updated_at=created_at,
        response_sent=lead_data['response_sent'],
        response_status=lead_data['response_status'],
        agent_id=lead_data['agent_id']
    )
    
    try:
        session.add(lead)
        session.commit()
        leads_created += 1
        
        agent_info = f" (Agente: {lead_data['agent_id']})" if lead_data['agent_id'] else " (Sin agente)"
        status_info = "✅ Enviado" if lead_data['response_sent'] and lead_data['response_status'] == 'sent' else \
                     "❌ Fallido" if lead_data['response_sent'] and lead_data['response_status'] == 'failed' else \
                     "⏳ Pendiente"
        
        print(f"   ✓ Creado lead: {lead_data['name']}{agent_info} - {status_info}")
    except IntegrityError as e:
        session.rollback()
        print(f"   ✗ Error creando lead {lead_data['name']}: {e}")

print(f"\n🎉 Resumen:")
print(f"   • Usuarios agentes: {len(agent_users)}")
print(f"   • Compañías: 1")
print(f"   • Credenciales: {len(agents_data)}")
print(f"   • Templates: 1")
print(f"   • Lead Sources: {len(lead_source_ids)}")
print(f"   • Leads creados: {leads_created}")

# Mostrar estadísticas por agente
print(f"\n📊 Leads por agente:")
for agent_id in ['agent1', 'agent2', None]:
    count = session.query(Lead).filter(Lead.agent_id == agent_id).count()
    agent_name = agent_id if agent_id else "Sin agente"
    print(f"   • {agent_name}: {count} leads")

session.close()
print("\n✅ Datos de prueba creados exitosamente!")
print("\n🔍 Ahora puedes:")
print("   1. Iniciar sesión como 'agent1' (password: agent123)")
print("   2. Ver el enlace 'My Leads' en el sidebar")
print("   3. Ver los 4 leads asignados a agent1")
print("   4. Probar búsqueda, filtros y paginación")
print("   5. Hacer clic en un lead para ver la página de detalle")