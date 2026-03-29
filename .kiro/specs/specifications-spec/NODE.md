# Especificación: Node.js / Express / TypeScript

## Estructura de Carpetas

```
src/
├── api/              # Rutas y controladores
├── application/      # Servicios de aplicación
├── domain/          # Lógica de negocio (use cases, interfaces)
├── infrastructure/  # Implementaciones (BD, externos)
└── config/          # Configuración
```

## Convenciones de Nombres

- **Archivos**: PascalCase para clases, camelCase para funciones
- **Clases**: `UserService`, `AuthRepository`, `GenerateAccessCode`
- **Interfaces**: Prefijo `I` → `IUserRepository`, `ITokenService`
- **Funciones**: camelCase → `generateToken()`, `validateUser()`
- **Constantes**: UPPER_SNAKE_CASE → `MAX_RETRIES`, `DEFAULT_TIMEOUT`

## Patrones de Código

### Servicios (Application Layer)

```typescript
export class UserService {
  constructor(private userRepository: IUserRepository) {}

  async registerUser(email: string, password: string): Promise<User> {
    // Lógica de aplicación
  }
}
```

### Repositorios (Infrastructure Layer)

```typescript
export class PrismaUserRepository implements IUserRepository {
  async findById(id: string): Promise<User | null> {
    return prisma.user.findUnique({ where: { id } });
  }
}
```

### Use Cases (Domain Layer)

```typescript
export class RegisterUser {
  constructor(private userRepository: IUserRepository) {}

  async execute(email: string, password: string): Promise<void> {
    // Validaciones y lógica de negocio
  }
}
```

### Rutas (API Layer)

```typescript
router.post('/users', async (req, res) => {
  try {
    const result = await userService.registerUser(req.body);
    res.json(result);
  } catch (error) {
    res.status(400).json({ error: error.message });
  }
});
```

## Dependencias Principales

- `express` - Framework web
- `typescript` - Tipado estático
- `prisma` - ORM
- `dotenv` - Variables de entorno
- `jest` - Testing
- `ts-node` - Ejecutar TypeScript

## Errores y Manejo

- Crear clases de error personalizadas
- Usar try-catch en servicios
- Retornar códigos HTTP apropiados
- Loguear errores importantes

## Ejemplo Mínimo

```typescript
// domain/user/repositories/IUserRepository.ts
export interface IUserRepository {
  create(data: CreateUserDTO): Promise<User>;
  findById(id: string): Promise<User | null>;
}

// infrastructure/persistence/PrismaUserRepository.ts
export class PrismaUserRepository implements IUserRepository {
  async create(data: CreateUserDTO): Promise<User> {
    return prisma.user.create({ data });
  }
}

// application/UserService.ts
export class UserService {
  constructor(private repo: IUserRepository) {}

  async registerUser(email: string): Promise<User> {
    return this.repo.create({ email });
  }
}
```

## Notas Importantes

- Siempre usar tipos TypeScript explícitos
- Inyección de dependencias en constructores
- Separación clara de capas (domain, application, infrastructure)
- Manejo de errores consistente
- Variables de entorno en `.env`
