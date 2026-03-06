"""
Gestión de usuarios – Gmail Lead Sync
======================================
Uso:
    python manage_users.py list                          # Listar usuarios
    python manage_users.py create <username> <password>  # Crear usuario
    python manage_users.py password <username> <password> # Cambiar password
    python manage_users.py delete <username>             # Eliminar usuario
"""

import sys
import bcrypt
import sqlite3
from datetime import datetime

DB_PATH = 'gmail_lead_sync.db'


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def get_conn():
    return sqlite3.connect(DB_PATH)


def list_users():
    conn = get_conn()
    rows = conn.execute(
        'SELECT id, username, role, created_at FROM users ORDER BY id'
    ).fetchall()
    conn.close()
    if not rows:
        print('No hay usuarios en la base de datos.')
        return
    print(f"\n{'ID':<5} {'Username':<20} {'Role':<10} {'Creado'}")
    print('-' * 60)
    for r in rows:
        print(f"{r[0]:<5} {r[1]:<20} {r[2]:<10} {r[3]}")
    print()


def create_user(username: str, password: str, role: str = 'admin'):
    conn = get_conn()
    existing = conn.execute(
        'SELECT id FROM users WHERE username = ?', (username,)
    ).fetchone()
    if existing:
        print(f"❌ El usuario '{username}' ya existe.")
        conn.close()
        return
    pw_hash = hash_password(password)
    conn.execute(
        'INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)',
        (username, pw_hash, role, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()
    print(f"✅ Usuario '{username}' creado correctamente (role: {role}).")


def change_password(username: str, new_password: str):
    conn = get_conn()
    row = conn.execute(
        'SELECT id FROM users WHERE username = ?', (username,)
    ).fetchone()
    if not row:
        print(f"❌ El usuario '{username}' no existe.")
        conn.close()
        return
    pw_hash = hash_password(new_password)
    conn.execute(
        'UPDATE users SET password_hash = ? WHERE username = ?',
        (pw_hash, username)
    )
    conn.commit()
    conn.close()
    print(f"✅ Password del usuario '{username}' actualizado correctamente.")


def delete_user(username: str):
    conn = get_conn()
    row = conn.execute(
        'SELECT id FROM users WHERE username = ?', (username,)
    ).fetchone()
    if not row:
        print(f"❌ El usuario '{username}' no existe.")
        conn.close()
        return
    confirm = input(f"¿Seguro que deseas eliminar '{username}'? (s/n): ").strip().lower()
    if confirm != 's':
        print("Cancelado.")
        conn.close()
        return
    conn.execute('DELETE FROM users WHERE username = ?', (username,))
    conn.commit()
    conn.close()
    print(f"✅ Usuario '{username}' eliminado.")


if __name__ == '__main__':
    args = sys.argv[1:]

    if not args or args[0] == 'list':
        list_users()

    elif args[0] == 'create' and len(args) == 3:
        create_user(args[1], args[2])

    elif args[0] == 'password' and len(args) == 3:
        change_password(args[1], args[2])

    elif args[0] == 'delete' and len(args) == 2:
        delete_user(args[1])

    else:
        print(__doc__)
