# Especificación General: Estándares del Proyecto

## Principios Generales

1. **Código limpio y legible** - Prioridad sobre optimización prematura
2. **Tipado fuerte** - TypeScript en todo el proyecto
3. **Separación de responsabilidades** - Cada módulo una tarea
4. **DRY (Don't Repeat Yourself)** - Reutilizar código
5. **SOLID principles** - Especialmente inyección de dependencias

## Estructura General del Proyecto

```
app-music/
├── src/
│   ├── api/              # Rutas y controladores HTTP
│   ├── application/      # Servicios de aplicación
│   ├── domain/          # Lógica de negocio pura
│   ├── infrastructure/  # Implementaciones técnicas
│   └── config/          # Configuración
├── prisma/              # Base de datos
├── docs/                # Documentación
├── scripts/             # Scripts de utilidad
└── tests/               # Tests
```

## Convenciones Globales

### Nombres de Archivos

- **Clases/Servicios**: PascalCase → `UserService.ts`, `AuthRepository.ts`
- **Funciones/Utilidades**: camelCase → `formatDate.ts`, `validateEmail.ts`
- **Tipos/Interfaces**: PascalCase → `User.ts`, `CreateUserDTO.ts`
- **Constantes**: UPPER_SNAKE_CASE → `MAX_RETRIES.ts`, `DEFAULT_TIMEOUT.ts`

### Estructura de Carpetas

- Una clase/interfaz principal por archivo
- Agrupar por dominio (auth, users, content, etc)
- Separar interfaces en carpeta `repositories/`
- Separar implementaciones en carpeta `persistence/`

### Comentarios y Documentación

```typescript
/**
 * Valida un email según RFC 5322
 * @param email - Email a validar
 * @returns true si es válido, false en caso contrario
 */
export const validateEmail = (email: string): boolean => {
  // Implementación
};
```

## Manejo de Errores

### Crear errores personalizados

```typescript
export class ValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ValidationError';
  }
}

export class NotFoundError extends Error {
  constructor(resource: string, id: string) {
    super(`${resource} with id ${id} not found`);
    this.name = 'NotFoundError';
  }
}
```

### Usar en servicios

```typescript
try {
  const user = await userRepository.findById(id);
  if (!user) throw new NotFoundError('User', id);
  return user;
} catch (error) {
  logger.error('Error fetching user', error);
  throw error;
}
```

## Variables de Entorno

Crear `.env` basado en `.env.example`:

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/app_music

# Server
PORT=3000
NODE_ENV=development

# Auth
JWT_SECRET=your-secret-key
JWT_EXPIRY=24h

# External Services
STRIPE_API_KEY=sk_test_...
```

## Logging

```typescript
import logger from './logger';

logger.info('User created', { userId: user.id });
logger.error('Database error', error);
logger.warn('Deprecated endpoint used');
```

## Testing

- Usar Jest para tests
- Nombrar archivos: `*.test.ts` o `*.spec.ts`
- Agrupar tests por funcionalidad
- Usar mocks para dependencias externas

```typescript
describe('UserService', () => {
  let userService: UserService;
  let mockRepository: jest.Mocked<IUserRepository>;

  beforeEach(() => {
    mockRepository = {
      findById: jest.fn(),
    };
    userService = new UserService(mockRepository);
  });

  it('should return user by id', async () => {
    const user = { id: '1', name: 'John' };
    mockRepository.findById.mockResolvedValue(user);

    const result = await userService.getUser('1');
    expect(result).toEqual(user);
  });
});
```

## Git Commits

Usar formato convencional:

```
feat: add user authentication
fix: resolve database connection issue
docs: update README
refactor: simplify UserService
test: add tests for AuthService
chore: update dependencies
```

## Performance

- Usar índices en BD para queries frecuentes
- Implementar paginación en listados
- Cachear datos cuando sea apropiado
- Evitar N+1 queries

## Seguridad

- Nunca commitear `.env` con valores reales
- Validar entrada del usuario
- Usar HTTPS en producción
- Hashear contraseñas (bcrypt)
- Implementar rate limiting
- Usar CORS apropiadamente

## Ejemplo de Flujo Completo

```typescript
// 1. Definir interfaz (domain)
export interface IUserRepository {
  create(data: CreateUserDTO): Promise<User>;
}

// 2. Implementar repositorio (infrastructure)
export class PrismaUserRepository implements IUserRepository {
  async create(data: CreateUserDTO): Promise<User> {
    return prisma.user.create({ data });
  }
}

// 3. Crear servicio (application)
export class UserService {
  constructor(private userRepository: IUserRepository) {}

  async registerUser(email: string, password: string): Promise<User> {
    const hashedPassword = await hashPassword(password);
    return this.userRepository.create({ email, password: hashedPassword });
  }
}

// 4. Exponer en ruta (api)
router.post('/users', async (req, res) => {
  try {
    const user = await userService.registerUser(req.body.email, req.body.password);
    res.status(201).json(user);
  } catch (error) {
    res.status(400).json({ error: error.message });
  }
});
```

## Checklist para Nuevo Código

- [ ] Tipos TypeScript explícitos
- [ ] Manejo de errores
- [ ] Documentación/comentarios
- [ ] Tests unitarios
- [ ] Sigue estructura de carpetas
- [ ] Nombres descriptivos
- [ ] Sin código duplicado
- [ ] Validación de entrada
