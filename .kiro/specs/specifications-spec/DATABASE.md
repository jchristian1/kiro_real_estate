# Especificación: Prisma / Base de Datos

## Estructura

```
prisma/
├── schema.prisma      # Definición del esquema
└── migrations/        # Historial de cambios
```

## Convenciones de Nombres

- **Modelos**: PascalCase singular → `User`, `Post`, `AccessCode`
- **Campos**: camelCase → `firstName`, `createdAt`, `isActive`
- **Relaciones**: Nombre descriptivo → `author`, `comments`, `accessGrants`
- **Índices**: Descriptivos → `@@index([userId])`, `@@unique([email])`

## Patrones de Esquema

### Modelo Básico

```prisma
model User {
  id        String   @id @default(cuid())
  email     String   @unique
  name      String
  password  String
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt

  // Relaciones
  posts     Post[]
  accessGrants AccessGrant[]

  @@index([email])
}
```

### Relaciones

```prisma
// One-to-Many
model User {
  id    String @id @default(cuid())
  posts Post[]
}

model Post {
  id     String @id @default(cuid())
  userId String
  user   User   @relation(fields: [userId], references: [id], onDelete: Cascade)
}

// Many-to-Many
model Student {
  id       String @id @default(cuid())
  courses  Course[]
}

model Course {
  id       String @id @default(cuid())
  students Student[]
}
```

### Enums

```prisma
enum Role {
  ADMIN
  USER
  MODERATOR
}

enum SubscriptionPlan {
  FREE
  PREMIUM
  ENTERPRISE
}

model User {
  id   String @id @default(cuid())
  role Role   @default(USER)
}
```

## Migraciones

### Crear migración

```bash
npx prisma migrate dev --name add_user_table
```

### Aplicar migraciones

```bash
npx prisma migrate deploy
```

### Resetear BD (desarrollo)

```bash
npx prisma migrate reset
```

## Tipos Generados

Prisma genera tipos automáticamente en `@prisma/client`:

```typescript
import { User, Post } from '@prisma/client';

const user: User = {
  id: '1',
  email: 'user@example.com',
  name: 'John',
  password: 'hashed',
  createdAt: new Date(),
  updatedAt: new Date(),
};
```

## Mejores Prácticas

- Usar `@default(now())` para timestamps
- Usar `@updatedAt` para campos de actualización
- Definir índices en campos frecuentemente consultados
- Usar `onDelete: Cascade` para relaciones críticas
- Usar enums para valores fijos
- Documentar cambios en migraciones

## Ejemplo Completo

```prisma
model User {
  id        String   @id @default(cuid())
  email     String   @unique
  name      String
  password  String
  role      Role     @default(USER)
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt

  posts     Post[]
  accessGrants AccessGrant[]

  @@index([email])
}

model Post {
  id        String   @id @default(cuid())
  title     String
  content   String
  published Boolean  @default(false)
  userId    String
  user      User     @relation(fields: [userId], references: [id], onDelete: Cascade)
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt

  @@index([userId])
}

model AccessGrant {
  id        String   @id @default(cuid())
  code      String   @unique
  userId    String
  user      User     @relation(fields: [userId], references: [id], onDelete: Cascade)
  expiresAt DateTime
  createdAt DateTime @default(now())

  @@index([userId])
  @@index([code])
}

enum Role {
  ADMIN
  USER
}
```

## Notas Importantes

- Siempre usar tipos generados por Prisma
- Mantener migraciones en control de versiones
- Documentar cambios de esquema
- Usar relaciones explícitas
- Considerar índices para performance
