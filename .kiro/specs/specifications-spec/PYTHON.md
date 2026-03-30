# Especificación: Python / FastAPI / Django

## Estructura de Carpetas

```
project/
├── app/
│   ├── api/              # Rutas y endpoints
│   ├── services/         # Lógica de negocio
│   ├── models/           # Modelos de BD
│   ├── schemas/          # Validación (Pydantic)
│   ├── repositories/     # Acceso a datos
│   ├── utils/            # Funciones utilitarias
│   └── config.py         # Configuración
├── tests/                # Tests
├── requirements.txt      # Dependencias
└── main.py              # Punto de entrada
```

## Convenciones de Nombres

- **Clases**: PascalCase → `UserService`, `AuthRepository`
- **Funciones**: snake_case → `get_user()`, `validate_email()`
- **Constantes**: UPPER_SNAKE_CASE → `MAX_RETRIES`, `DEFAULT_TIMEOUT`
- **Archivos**: snake_case → `user_service.py`, `auth_repository.py`
- **Variables**: snake_case → `user_id`, `is_active`

## Patrones de Código

### FastAPI - Endpoint

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/users", tags=["users"])

class UserCreate(BaseModel):
    email: str
    name: str

@router.post("/")
async def create_user(user: UserCreate):
    """Crear nuevo usuario"""
    try:
        new_user = await user_service.register(user.email, user.name)
        return new_user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

### Servicio

```python
class UserService:
    def __init__(self, repository: UserRepository):
        self.repository = repository

    async def register(self, email: str, name: str) -> User:
        """Registrar nuevo usuario"""
        if await self.repository.find_by_email(email):
            raise ValueError("Email already exists")

        user = User(email=email, name=name)
        return await self.repository.create(user)
```

### Repositorio

```python
from sqlalchemy.orm import Session

class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    async def create(self, user: User) -> User:
        """Crear usuario en BD"""
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    async def find_by_email(self, email: str) -> User | None:
        """Buscar usuario por email"""
        return self.db.query(User).filter(User.email == email).first()
```

### Modelos SQLAlchemy

```python
from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### Schemas Pydantic

```python
from pydantic import BaseModel, EmailStr
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    name: str

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
```

## Dependencias Principales

- `fastapi` - Framework web
- `sqlalchemy` - ORM
- `pydantic` - Validación
- `python-dotenv` - Variables de entorno
- `pytest` - Testing
- `httpx` - HTTP client para tests

## Manejo de Errores

```python
class ValidationError(Exception):
    """Error de validación"""
    pass

class NotFoundError(Exception):
    """Recurso no encontrado"""
    pass

# En endpoints
@router.get("/{user_id}")
async def get_user(user_id: str):
    try:
        user = await user_service.get_user(user_id)
        return user
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")
```

## Testing

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_user():
    """Test crear usuario"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/users/",
            json={"email": "test@example.com", "name": "Test User"}
        )
        assert response.status_code == 201
        assert response.json()["email"] == "test@example.com"

@pytest.mark.asyncio
async def test_user_not_found():
    """Test usuario no encontrado"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/users/nonexistent")
        assert response.status_code == 404
```

## Ejemplo Mínimo

```python
# main.py
from fastapi import FastAPI
from app.api import users

app = FastAPI()
app.include_router(users.router)

# app/api/users.py
from fastapi import APIRouter
from app.services.user_service import UserService
from app.schemas import UserCreate, UserResponse

router = APIRouter(prefix="/users", tags=["users"])
user_service = UserService()

@router.post("/", response_model=UserResponse)
async def create_user(user: UserCreate):
    return await user_service.register(user.email, user.name)

# app/services/user_service.py
class UserService:
    async def register(self, email: str, name: str):
        # Lógica de negocio
        pass
```

## Notas Importantes

- Usar type hints en todas las funciones
- Validar con Pydantic
- Usar async/await para operaciones I/O
- Inyección de dependencias en FastAPI
- Documentación automática con docstrings
- Logging estructurado
- Variables de entorno para configuración
