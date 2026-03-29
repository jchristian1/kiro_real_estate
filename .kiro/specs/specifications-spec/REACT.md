# Especificación: React / TypeScript

## Estructura de Carpetas

```
src/
├── models/
│   ├── components/
│   │   ├── userCard.ts # Tipos
│   │   ├── LoginForm.ts
│   │   ├── User.ts
│   │   ├── Card.ts
│   │   └── index.ts
│   ├── pages/
│   │   ├── HomePage/
│   │   │   ├── HomePage.types.ts
│   │   │   ├── PageState.ts
│   │   │   ├── PageProps.ts
│   │   └── index.ts
│   │   ├── UserPage/
│   │   │   ├── UserPage.types.ts
│   │   └── index.ts
│   ├── shared/
│   │   ├── API.ts
│   │   ├── Common.ts
│   │   ├── User.ts
│   │   ├── Auth.ts
│   └── index.ts                     # Barrel file
├── components/
│   ├── UserCard/
│   │   ├── index.tsx                    # Componente principal
│   │   ├── index.module.css             # Estilos            
│   │   └── components/                  # Sub-componentes (solo para este componente)
│   │       ├── UserCardHeader/
│   │       │   ├── index.tsx
│   │       │   └── index.module.css
│   │       └── index.ts                 # Barrel file
│   ├── LoginForm/
│   │   ├── index.tsx
│   │   ├── index.module.css
│   │   └── components/
│   │       ├── FormInput/
│   │       │   ├── index.tsx
│   │       │   └── index.module.css
│   │       └── index.ts
│   └── index.ts                         # Barrel file
├── pages/
│   ├── HomePage/
│   │   ├── index.tsx
│   │   ├── index.module.css
│   │   └── components/                  # Sub-componentes (solo para esta página)
│   │       ├── HeroSection/
│   │       │   ├── index.tsx
│   │       │   └── index.module.css
│   │       └── index.ts
│   ├── UserPage/
│   │   ├── index.tsx
│   │   ├── index.module.css
│   │   └── components/
│   │       └── index.ts
│   └── index.ts                         # Barrel file
├── shared/
│   ├── hooks/
│   │   ├── useAuth.ts
│   │   ├── useFetch.ts
│   │   └── index.ts                     # Barrel file
│   ├── services/
│   │   ├── userService.ts
│   │   ├── authService.ts
│   │   └── index.ts                     # Barrel file
│   ├── context/
│   │   ├── AuthContext.tsx
│   │   ├── ThemeContext.tsx
│   │   └── index.ts                     # Barrel file
│   ├── providers/
│   │   ├── AuthProvider.tsx
│   │   ├── ThemeProvider.tsx
│   │   └── index.ts                     # Barrel file
│   ├── utils/
│   │   ├── formatDate.ts
│   │   ├── validateEmail.ts
│   │   └── index.ts                     # Barrel file
│   ├── config/
│   │   ├── api.ts                       # Configuración de API
│   │   ├── constants.ts                 # Constantes globales
│   │   └── index.ts                     # Barrel file
├── styles/
│   ├── globals.css                  # Estilos globales
│   ├── variables.css                # Variables CSS
│   └── reset.css                    # Reset de estilos
└── App.tsx
```

## Convenciones de Nombres

- **Carpetas de componentes**: PascalCase → `UserCard/`, `LoginForm/`
- **Archivo principal**: Siempre `index.tsx`
- **Estilos**: Siempre `index.module.css`
- **Modelos**: `ModelName.ts` → `User.ts`, `Card.ts` (en carpeta `models/`)
- **Hooks**: camelCase con prefijo `use` → `useAuth.ts`, `useFetch.ts`
- **Props interfaces**: `ComponentNameProps` → `UserCardProps`
- **Funciones**: camelCase → `formatDate()`, `validateEmail()`
- **Sub-componentes**: Carpeta `components/` dentro del componente padre

## Patrones de Código

### Estructura de Componente

```
UserCard/
├── index.tsx           # Componente principal
└── index.module.css    # Estilos scoped
```

### Componente (index.tsx)

```typescript
import styles from './index.module.css';
import type { UserCardProps } from './UserCard.types';

export const UserCard: React.FC<UserCardProps> = ({ userId, onDelete }) => {
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    // Cargar usuario
  }, [userId]);

  return (
    <div className={styles.container}>
      <h2 className={styles.title}>{user?.name}</h2>
      <button onClick={onDelete} className={styles.deleteBtn}>
        Eliminar
      </button>
    </div>
  );
};
```

### Tipos (userCard.ts)

```typescript
export interface UserCardProps {
  userId: string;
  onDelete?: () => void;
}
```

### Estilos (index.module.css)

```css
.container {
  padding: 16px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  background-color: #fff;
}

.title {
  margin: 0 0 12px 0;
  font-size: 18px;
  font-weight: 600;
}

.deleteBtn {
  padding: 8px 16px;
  background-color: #ff4444;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}
```

### Barrel File (components/index.ts)

```typescript
export { UserCard } from './UserCard';
export { LoginForm } from './LoginForm';
export { Header } from './Header';
```

### Importar desde barrel

```typescript
// ✅ Bien
import { UserCard, LoginForm } from '@/components';

// ❌ Evitar
import { UserCard } from '@/components/UserCard/index';
```

### Sub-componentes (Componentes anidados)

Cuando un componente tiene sub-componentes que **solo él usa**, crearlos en una carpeta `components/` dentro del componente padre:

```
UserCard/
├── index.tsx
├── index.module.css
└── index.ts                # Barrel file
└── components/
    ├── UserCardHeader/
    │   ├── index.tsx
    │   ├── index.module.css
    ├── UserCardBody/
    │   ├── index.tsx
    │   ├── index.module.css
    └── index.ts                # Barrel file
```

**UserCard/components/UserCardHeader/index.tsx**

```typescript
import styles from './index.module.css';
import type { UserCardHeaderProps } from './UserCardHeader.types';

export const UserCardHeader: React.FC<UserCardHeaderProps> = ({ title }) => (
  <div className={styles.header}>
    <h3>{title}</h3>
  </div>
);
```

**UserCard/components/index.ts** (Barrel file)

```typescript
export { UserCardHeader } from './UserCardHeader';
export { UserCardBody } from './UserCardBody';
```

**UserCard/index.tsx** (Importar sub-componentes)

```typescript
import styles from './index.module.css';
import type { UserCardProps } from './UserCard.types';
import { UserCardHeader, UserCardBody } from './components';

export const UserCard: React.FC<UserCardProps> = ({ user, onDelete }) => (
  <div className={styles.container}>
    <UserCardHeader title={user.name} />
    <UserCardBody user={user} onDelete={onDelete} />
  </div>
);
```

### Modelos (Models)

Modelos son tipos/interfaces que se comparten dentro de un nivel (components, pages, shared). Crear carpeta `models/`:

**components/models/components/user.ts**

```typescript
export interface UserCardModel {
  id: string;
  name: string;
  email: string;
  avatar?: string;
}

export interface UserCardState {
  isLoading: boolean;
  error?: string;
}
```

**components/models/index.ts** (Barrel file)

```typescript
export type { UserCardModel, UserCardState } from './User';
export type { CardProps } from './Card';
```

**components/UserCard/index.tsx** (Usar modelos)

```typescript
import type { UserCardModel } from '@/components/models';

interface UserCardProps {
  user: UserCardModel;
  onDelete?: () => void;
}

export const UserCard: React.FC<UserCardProps> = ({ user, onDelete }) => (
  <div>{user.name}</div>
);
```

**Diferencia entre `types/` y `models/`:**

- **`types/`**: Tipos específicos de un componente/página (props, state local)
- **`models/`**: Modelos de datos compartidos dentro del nivel (components, pages, shared)

### Custom Hooks

```typescript
export const useAuth = () => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(false);

  const login = async (email: string, password: string) => {
    setLoading(true);
    try {
      const response = await api.post('/auth/login', { email, password });
      setUser(response.data);
    } finally {
      setLoading(false);
    }
  };

  return { user, loading, login };
};
```

### Servicios API

```typescript
export const userService = {
  getUser: (id: string) => api.get(`/users/${id}`),
  createUser: (data: CreateUserDTO) => api.post('/users', data),
  updateUser: (id: string, data: UpdateUserDTO) => api.put(`/users/${id}`, data),
};
```

### Tipos Globales

```typescript
// types/User.ts
export interface User {
  id: string;
  email: string;
  name: string;
  createdAt: Date;
}

export interface CreateUserDTO {
  email: string;
  name: string;
}
```

## Dependencias Principales

- `react` - Framework
- `react-router-dom` - Routing
- `axios` o `fetch` - HTTP client
- `typescript` - Tipado
- `@testing-library/react` - Testing

## Carpeta `shared/` - Código Reutilizable

La carpeta `shared/` centraliza todo el código que se usa en múltiples lugares:

### `shared/hooks/`

Custom hooks reutilizables en toda la app

```typescript
// useAuth.ts - Hook para autenticación
// useFetch.ts - Hook para llamadas HTTP
// useLocalStorage.ts - Hook para localStorage
```

### `shared/services/`

Servicios para llamadas a API y lógica externa

```typescript
// userService.ts - Operaciones de usuarios
// authService.ts - Operaciones de autenticación
// apiClient.ts - Cliente HTTP configurado
```

### `shared/context/`

Contextos de React para estado global

```typescript
// AuthContext.tsx - Contexto de autenticación
// ThemeContext.tsx - Contexto de tema
```

### `shared/providers/`

Componentes proveedores que envuelven la app

```typescript
// AuthProvider.tsx - Proveedor de autenticación
// ThemeProvider.tsx - Proveedor de tema
```

### `shared/config/`

Configuración global de la app

```typescript
// api.ts - Configuración de axios/fetch
// constants.ts - Constantes globales (URLs, timeouts, etc)
// env.ts - Variables de entorno
```

### `shared/utils/`

Funciones utilitarias reutilizables

```typescript
// formatDate.ts - Formatear fechas
// validateEmail.ts - Validar emails
// parseError.ts - Parsear errores de API
```

### `shared/styles/`

Estilos globales

```typescript
// globals.css - Estilos globales
// variables.css - Variables CSS (colores, espacios, etc)
// reset.css - Reset de estilos del navegador
```

## Mejores Prácticas

- Componentes pequeños y reutilizables
- Props bien tipadas (siempre en archivo `.types.ts`)
- Usar hooks en lugar de clases
- Memoizar componentes si es necesario (`React.memo`)
- Separar lógica en custom hooks
- Manejo de errores en servicios
- **Usar barrel files** para importaciones limpias
- **Estilos scoped** con CSS Modules (evita conflictos)
- **Una carpeta por componente** para mejor organización
- Tipos globales y Tipos locales en `models/` segun estructura de carpetas
- **Centralizar código reutilizable en `shared/`**
- **No duplicar lógica** - si se usa en 2+ lugares, va en `shared/`
- **Importar desde `@/shared/`** en lugar de rutas relativas
- **Mantener `shared/` limpio** - solo código verdaderamente reutilizable
- **Sub-componentes en carpeta `components/`** dentro del componente padre
- **Usar modelos para datos**, tipos para props/state local
- **Evitar anidación profunda** - máximo 2 niveles de sub-componentes

## Ejemplo Mínimo

```
src/
├── models/
│   ├── components/
│   │   ├── userCard.ts # Tipos
│   │   ├── LoginForm.ts
│   │   ├── User.ts
│   │   ├── Card.ts
│   │   └── index.ts
│   ├── pages/
│   │   ├── HomePage/
│   │   │   ├── HomePage.types.ts
│   │   │   ├── PageState.ts
│   │   │   ├── PageProps.ts
│   │   └── index.ts
│   │   ├── UserPage/
│   │   │   ├── UserPage.types.ts
│   │   └── index.ts
│   ├── shared/
│   │   ├── API.ts
│   │   ├── Common.ts
│   │   ├── User.ts
│   │   ├── Auth.ts
│   └── index.ts                     # Barrel file
├── components/
│   ├── UserCard/
│   │   ├── index.tsx                    # Componente principal
│   │   ├── index.module.css             # Estilos            
│   │   └── components/                  # Sub-componentes (solo para este componente)
│   │       ├── UserCardHeader/
│   │       │   ├── index.tsx
│   │       │   └── index.module.css
│   │       └── index.ts                 # Barrel file
│   ├── LoginForm/
│   │   ├── index.tsx
│   │   ├── index.module.css
│   │   └── components/
│   │       ├── FormInput/
│   │       │   ├── index.tsx
│   │       │   └── index.module.css
│   │       └── index.ts
│   └── index.ts                         # Barrel file
├── pages/
│   ├── HomePage/
│   │   ├── index.tsx
│   │   ├── index.module.css
│   │   └── components/                  # Sub-componentes (solo para esta página)
│   │       ├── HeroSection/
│   │       │   ├── index.tsx
│   │       │   └── index.module.css
│   │       └── index.ts
│   ├── UserPage/
│   │   ├── index.tsx
│   │   ├── index.module.css
│   │   └── components/
│   │       └── index.ts
│   └── index.ts                         # Barrel file
├── shared/
│   ├── hooks/
│   │   ├── useAuth.ts
│   │   ├── useFetch.ts
│   │   └── index.ts                     # Barrel file
│   ├── services/
│   │   ├── userService.ts
│   │   ├── authService.ts
│   │   └── index.ts                     # Barrel file
│   ├── context/
│   │   ├── AuthContext.tsx
│   │   ├── ThemeContext.tsx
│   │   └── index.ts                     # Barrel file
│   ├── providers/
│   │   ├── AuthProvider.tsx
│   │   ├── ThemeProvider.tsx
│   │   └── index.ts                     # Barrel file
│   ├── utils/
│   │   ├── formatDate.ts
│   │   ├── validateEmail.ts
│   │   └── index.ts                     # Barrel file
│   ├── config/
│   │   ├── api.ts                       # Configuración de API
│   │   ├── constants.ts                 # Constantes globales
│   │   └── index.ts                     # Barrel file
├── styles/
│   ├── globals.css                  # Estilos globales
│   ├── variables.css                # Variables CSS
│   └── reset.css                    # Reset de estilos
└── App.tsx
```

**shared/types/User.ts**

```typescript
export interface User {
  id: string;
  name: string;
}
```

**components/models/User.ts** (Modelos compartidos en components)

```typescript
export interface UserProfileModel {
  id: string;
  name: string;
  email: string;
  avatar?: string;
}
```

**components/models/index.ts** (Barrel file)

```typescript
export type { UserProfileModel } from './User';
```

**shared/services/userService.ts**

```typescript
import { User } from '@/shared/types';

export const userService = {
  getUser: (id: string): Promise<User> => fetch(`/api/users/${id}`).then((r) => r.json()),
};
```

**shared/hooks/useUser.ts**

```typescript
import { useState, useEffect } from 'react';
import { User } from '@/shared/types';
import { userService } from '@/shared/services';

export const useUser = (id: string) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    userService
      .getUser(id)
      .then(setUser)
      .finally(() => setLoading(false));
  }, [id]);

  return { user, loading };
};
```

**shared/hooks/index.ts** (Barrel file)

```typescript
export { useUser } from './useUser';
```

**shared/services/index.ts** (Barrel file)

```typescript
export { userService } from './userService';
```

**shared/types/index.ts** (Barrel file)

```typescript
export type { User } from './User';
```

**components/UserProfile/components/UserHeader/UserHeader.types.ts**

```typescript
export interface UserHeaderProps {
  name: string;
  avatar?: string;
}
```

**components/UserProfile/components/UserHeader/index.tsx**

```typescript
import styles from './index.module.css';
import type { UserHeaderProps } from './UserHeader.types';

export const UserHeader: React.FC<UserHeaderProps> = ({ name, avatar }) => (
  <div className={styles.header}>
    {avatar && <img src={avatar} alt={name} className={styles.avatar} />}
    <h2 className={styles.name}>{name}</h2>
  </div>
);
```

**components/UserProfile/components/index.ts** (Barrel file)

```typescript
export { UserHeader } from './UserHeader';
```

**components/UserProfile/UserProfile.types.ts**

```typescript
export interface UserProfileProps {
  userId: string;
}
```

**components/UserProfile/index.tsx**

```typescript
import styles from './index.module.css';
import type { UserProfileProps } from './UserProfile.types';
import { useUser } from '@/shared/hooks';
import { UserHeader } from './components';

export const UserProfile: React.FC<UserProfileProps> = ({ userId }) => {
  const { user, loading } = useUser(userId);

  if (loading) return <div className={styles.loading}>Cargando...</div>;
  if (!user) return <div>Usuario no encontrado</div>;

  return (
    <div className={styles.profile}>
      <UserHeader name={user.name} />
      <p className={styles.email}>{user.email}</p>
    </div>
  );
};
```

**components/UserProfile/index.module.css**

```css
.profile {
  padding: 16px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
}

.loading {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100px;
}

.email {
  margin-top: 8px;
  color: #666;
}
```

**components/index.ts** (Barrel file)

```typescript
export { UserProfile } from './UserProfile';
```

**App.tsx**

```typescript
import { UserProvider } from '@/shared/providers';
import { UserProfile } from '@/components';

export function App() {
  return (
    <UserProvider>
      <UserProfile userId="1" />
    </UserProvider>
  );
}
```

**components/UserProfile/UserProfile.types.ts**

```typescript
export interface UserProfileProps {
  userId: string;
}
```

**components/UserProfile/index.tsx**

```typescript
import styles from './index.module.css';
import type { UserProfileProps } from './UserProfile.types';
import { useUser } from '@/shared/hooks';

export const UserProfile: React.FC<UserProfileProps> = ({ userId }) => {
  const { user, loading } = useUser(userId);

  if (loading) return <div className={styles.loading}>Cargando...</div>;
  return <div className={styles.profile}>{user?.name}</div>;
};
```

**components/UserProfile/index.module.css**

```css
.loading {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100px;
}

.profile {
  padding: 16px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
}
```

**components/index.ts** (Barrel file)

```typescript
export { UserProfile } from './UserProfile';
```

**App.tsx**

```typescript
import { UserProvider } from '@/shared/providers';
import { HomePage } from '@/pages';

export function App() {
  return (
    <UserProvider>
      <HomePage />
    </UserProvider>
  );
}
```

## Notas Importantes

- Siempre tipificar props e interfaces
- Usar `React.FC` para componentes funcionales
- Evitar props drilling (usar Context si es necesario)
- Manejar estados de carga y error
- Limpiar efectos (return en useEffect)
- **Cada componente en su propia carpeta** con `index.tsx` e `index.module.css`
- **Importar siempre desde barrel files** (`@/components`, `@/shared/hooks`, `@/shared/services`)
- **Tipos específicos del componente** en `ComponentName.types.ts`
- **Modelos compartidos en `models/`** a nivel de components, pages y shared
- **Tipos globales en `shared/types/`** si se usan en múltiples componentes
- **CSS Modules** para evitar conflictos de estilos globales
- **Mantener estructura consistente** en todos los componentes
- **Carpeta `shared/`** centraliza: hooks, services, context, providers, utils, config, types, models
- **Importaciones desde `@/shared/`** para código reutilizable
- **Sub-componentes en carpeta `components/`** dentro del componente padre si solo él los usa
- **Diferencia tipos vs modelos**: tipos = props/state local, modelos = datos compartidos en el nivel
- **No duplicar componentes** - si se usa en 2+ lugares, va en `@/components`
