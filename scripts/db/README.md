# Database Management Scripts

Utilidades para gestionar la base de datos del proyecto.

## Scripts disponibles

### `create_agent_user.py`
Crea usuarios agentes en la base de datos.

```bash
python scripts/db/create_agent_user.py
```

**Crea:**
- `agent1` (password: `agent123`)
- `agent2` (password: `agent123`)

### `create_test_leads.py`
Crea datos de prueba: compañías, credenciales, templates, lead sources y leads.

```bash
python scripts/db/create_test_leads.py
```

**Crea:**
- 1 compañía
- 2 credenciales para agentes
- 1 template
- 2 lead sources
- 9 leads de prueba

### `check_database.py`
Verifica el estado de la base de datos y lista usuarios y leads.

```bash
python scripts/db/check_database.py
```

### `debug_api_db.py`
Diagnostica qué base de datos está usando la API.

```bash
python scripts/db/debug_api_db.py
```

### `test_api_connection.py`
Prueba la conexión a la base de datos desde la perspectiva de la API.

```bash
python scripts/db/test_api_connection.py
```

### `manage_users.py`
Gestiona usuarios en la base de datos (crear, actualizar, eliminar).

```bash
python scripts/db/manage_users.py
```

## Requisitos

- Python 3.10+
- SQLAlchemy
- bcrypt
- python-dotenv

## Configuración

Asegúrate de que el archivo `.env` esté en la raíz del proyecto con las variables de entorno correctas:

```
DATABASE_URL=sqlite:///./gmail_lead_sync.db
ENCRYPTION_KEY=<tu-clave-de-encriptacion>
SECRET_KEY=<tu-clave-secreta>
```

## Notas de seguridad

- ⚠️ **NO subir** archivos `.db` a Git
- ⚠️ **NO subir** archivos `.env` a Git
- ✅ **SÍ subir** estos scripts de utilidad
- ✅ **SÍ subir** `.env.example` como referencia

## Uso en desarrollo

1. Ejecutar migraciones:
   ```bash
   alembic upgrade head
   ```

2. Crear usuarios:
   ```bash
   python scripts/db/create_agent_user.py
   python create_user.py  # Para admin
   ```

3. Crear datos de prueba:
   ```bash
   python scripts/db/create_test_leads.py
   ```

4. Verificar estado:
   ```bash
   python scripts/db/check_database.py
   ```
