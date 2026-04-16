## 📖 MANUAL COMPLETO DE ALEMBIC - Sistema RRHH Bolivia

---

## ¿QUÉ ES ALEMBIC?

Alembic es una **herramienta de versionamiento de bases de datos**. En simples palabras:

```
Tu código Python (Modelos SQLAlchemy)
              ↓
        Alembic detecta cambios
              ↓
Genera un script SQL automático
              ↓
      Aplica cambios a PostgreSQL
```

**Analogía:** Es como Git, pero para cambios en la estructura de la BD en lugar de código.

---

## ¿POR QUÉ LO USAMOS?

### Sin Alembic ❌
```
1. Cambias un modelo en Python
2. Tienes que ejecutar manualmente SQL:
   CREATE TABLE nueva_tabla (
       id SERIAL PRIMARY KEY,
       nombre VARCHAR(100)
   );
3. Si te equivocas, tienes que deshacer manualmente
4. En la próxima versión, ¿qué cambios hice? No hay registro.
```

### Con Alembic ✅
```
1. Cambias un modelo en Python
2. Alembic DETECTA automáticamente los cambios
3. Genera un archivo Python con el SQL (revision file)
4. Lo aplicas con un comando
5. Historial completo: puedes ver qué cambió cada semana
```

---

## FLUJO DE TRABAJO CON ALEMBIC

```
┌─────────────────────────────────────────────────────────┐
│                    SEMANA DE DESARROLLO                │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  PASO 1: EDITAR MODELOS (en Python)                    │
│  ────────────────────────────────────────              │
│  Ejemplo: Agregar un nuevo modelo "Horario"            │
│                                                          │
│  archivo: app/features/attendance/horario/models.py   │
│  class Horario(Base):                                  │
│      __tablename__ = "horario"                         │
│      id: Mapped[int] = ...                             │
│      nombre: Mapped[str] = ...                         │
│                                                          │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│  PASO 2: REGISTRAR EL MODELO EN ALEMBIC (env.py)      │
│  ─────────────────────────────────────────────────     │
│  Abrir: alembic/env.py                                 │
│  Agregar import:                                        │
│     from app.features.attendance.horario.models \     │
│     import Horario  # noqa: F401                       │
│                                                          │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│  PASO 3: GENERAR MIGRACIÓN CON AUTOGENERATE            │
│  ──────────────────────────────────────────            │
│  Terminal:                                              │
│  $ alembic revision --autogenerate -m "add_horario"  │
│                                                      │
│  Crea: alembic/versions/xxxxx_add_horario.py         │
│  Este archivo contiene el SQL generado automáticamente │
│                                                          │
│  ⚠️  IMPORTANTE: REVISAR el archivo generado antes     │
│     de aplicarlo (a veces Alembic no es perfecto)     │
│                                                          │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│  PASO 4: APLICAR LA MIGRACIÓN A LA BD                 │
│  ──────────────────────────────────────              │
│  Terminal:                                              │
│  $ alembic upgrade head                               │
│                                                          │
│  Esto ejecuta el SQL en PostgreSQL y actualiza         │
│  la tabla de versiones de Alembic                      │
│                                                          │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│  PASO 5: VERIFICAR EN BASE DE DATOS                   │
│  ─────────────────────────────────────                │
│  Terminal (PostgreSQL):                                │
│  $ psql -U postgres -d rrhh_bolivia                   │
│  # \dt rrhh.*                  (listar tablas)         │
│  # SELECT * FROM rrhh.horario;  (verificar datos)     │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## COMANDOS ALEMBIC EXPLICADOS

### 1️⃣ GENERAR MIGRACIÓN (Lo más importante)

```bash
alembic revision --autogenerate -m "descripcion_del_cambio"
```

**¿Qué hace?**
- Compara tus modelos Python actuales con el estado de la BD
- Detecta qué cambió
- Genera un archivo con el SQL necesario

**Desglose del comando:**
- `alembic revision` = "Crea un nuevo archivo de migración"
- `--autogenerate` = "Detecta cambios automáticamente"
- `-m "descripcion"` = "Mensaje para recordar qué cambió"

**Ejemplo real:**
```bash
# Agregaste un nuevo campo a Empleado
alembic revision --autogenerate -m "add_email_field_to_empleado"

# Output:
# Generating /path/to/alembic/versions/abc123_add_email_field_to_empleado.py
# Detected added column 'empleado.email'
```

**Archivo generado:**
```python
# alembic/versions/abc123_add_email_field_to_empleado.py

def upgrade() -> None:
    # Cambios a APLICAR
    op.add_column('empleado',
        sa.Column('email', sa.String(length=150), nullable=True),
        schema='rrhh'
    )

def downgrade() -> None:
    # Cambios a DESHACER (si usamos: alembic downgrade -1)
    op.drop_column('empleado', 'email', schema='rrhh')
```

---

### 2️⃣ APLICAR MIGRATIONS (Hacer cambios reales en BD)

```bash
alembic upgrade head
```

**¿Qué hace?**
- Ejecuta TODAS las migraciones pendientes en PostgreSQL
- "head" significa "hasta la última versión"

**Analogía:** Es como `git pull` pero para la BD.

**Estados posibles:**

```bash
# Ver estado actual
alembic current
# Output: a1b2c3d4e5f6 (head)
# Significa: Ya estás en la última versión

# Ver historial de migraciones
alembic history
# Output:
# a1b2c3d4e5f6 (head)
# 7f6e5d4c3b2a
# 6a65fa2dd1f5 (branchpoint)
```

---

### 3️⃣ DESHACER CAMBIOS (Rollback)

```bash
# Deshacer la última migración
alembic downgrade -1

# Deshacer 3 migraciones
alembic downgrade -3

# Ir a una migración específica
alembic downgrade 7f6e5d4c3b2a
```

**Cuidado:** Esto BORRA datos de la BD si se eliminan columnas.

---

### 4️⃣ VER INFORMACIÓN

```bash
# ¿En qué versión estoy?
alembic current

# ¿Qué cambios se han hecho?
alembic history

# ¿Qué cambios hay pendientes?
alembic history | grep "new"  # (Linux/Mac)
```

---

## ESTRUCTURA DE UN ARCHIVO DE MIGRACIÓN

Cuando se genera una migración, Alembic crea un archivo como este:

```python
# alembic/versions/6a65fa2dd1f5_init_modelos_base.py

"""init_modelos_base

Revision ID: 6a65fa2dd1f5
Revises:
Create Date: 2026-03-23 12:24:24.649561

"""
from alembic import op
import sqlalchemy as sa

# Identificadores de la migración
revision: str = '6a65fa2dd1f5'
down_revision: Union[str, None] = None  # Esta es la PRIMERA migración
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """CAMBIOS A APLICAR cuando ejecutamos: alembic upgrade head"""

    # Crear tabla 'complemento_dep'
    op.create_table('complemento_dep',
        sa.Column('codigo', sa.String(length=2), nullable=False),
        sa.Column('nombre_departamento', sa.String(length=50), nullable=False),
        sa.Column('activo', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('codigo', name=op.f('pk_complemento_dep')),
        schema='rrhh'
    )


def downgrade() -> None:
    """CAMBIOS A DESHACER cuando ejecutamos: alembic downgrade"""

    # Borrar tabla 'complemento_dep'
    op.drop_table('empleado', schema='rrhh')
    op.drop_table('complemento_dep', schema='rrhh')
```

**Partes importantes:**
- `revision` = ID único de esta migración (automático)
- `down_revision` = Migración anterior (None si es la primera)
- `upgrade()` = Cambios A APLICAR (hacia adelante)
- `downgrade()` = Cambios A DESHACER (hacia atrás)

---

## FLUJO COMPLETO: EJEMPLO PRÁCTICO

Supongamos que en **Semana 2** necesitas agregar el modelo `Usuario`.

### Paso 1: Crear el modelo
```python
# app/features/auth/usuario/models.py

from app.db.base import Base

class Usuario(Base):
    """Tabla: rrhh.usuario"""
    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
```

### Paso 2: Registrar en alembic/env.py
```python
# Abrir alembic/env.py
# Agregar DESPUÉS de la línea: from app.features.employees.empleado.models import Empleado

from app.features.auth.usuario.models import Usuario  # noqa: F401
```

### Paso 3: Generar migración
```bash
source venv/Scripts/activate

# En la terminal:
alembic revision --autogenerate -m "semana2_add_usuario_model"

# Output:
# Generating C:\...\alembic\versions\abc123def456_semana2_add_usuario_model.py
# Detected added table 'rrhh.usuario'
```

### Paso 4: REVISAR el archivo generado
```bash
# Abrir: alembic/versions/abc123def456_semana2_add_usuario_model.py
# Verificar que el SQL sea correcto

# Ejemplo de lo que ves:
def upgrade() -> None:
    op.create_table('usuario',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('username', sa.String(length=100), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('activo', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_usuario')),
        sa.UniqueConstraint('username', name=op.f('uq_usuario_username')),
        schema='rrhh'
    )
```

✅ Si se ve bien, continúa. ❌ Si hay errores, edita el archivo.

### Paso 5: Aplicar migración
```bash
alembic upgrade head

# Output:
# INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
# INFO  [alembic.runtime.migration] Will assume transactional DDL.
# INFO  [alembic.runtime.migration] Running upgrade 6a65fa2dd1f5 -> abc123def456, semana2_add_usuario_model
```

### Paso 6: Verificar en PostgreSQL
```bash
# Conectar a la BD
psql -U postgres -d rrhh_bolivia

# Ver las tablas
\dt rrhh.*

# Ver la tabla usuario
SELECT * FROM rrhh.usuario;

# Ver la estructura de la tabla
\d rrhh.usuario

# Salir
\q
```

---

## ⚠️ ERRORES COMUNES Y SOLUCIONES

### Error 1: "No se detectaron cambios"
```
$ alembic revision --autogenerate -m "cambios"
# Output: No changes detected
```

**Causas posibles:**
1. ✗ El modelo no está importado en `alembic/env.py`
2. ✗ Alembic está comparando con una versión anterior de tu código
3. ✗ No cambiaste nada en realidad

**Solución:**
```bash
# 1. Verificar que el modelo está en alembic/env.py
grep "from app.features.auth.usuario.models import Usuario" alembic/env.py

# 2. Si no está, agrégalo y reintentar
alembic revision --autogenerate -m "semana2_add_usuario"
```

---

### Error 2: "Conflicto de migraciones"
```
alembic upgrade head
# ERROR: Could not find base revision or resolved heads in model metadata
```

**Causa:** Dos migraciones apuntan al mismo padre (conflicto de merge).

**Solución:** Esto ocurre si dos personas/ramas crean migraciones simultáneamente. Para este proyecto (una sola persona), no debería ocurrir.

---

### Error 3: "Migración falla al aplicar"
```
alembic upgrade head
# ERROR: (pgm_syntax_error) syntax error in type definition...
```

**Causa:** El SQL generado por Alembic tiene un error. Esto pasa raramente.

**Solución:**
```bash
# 1. Ver qué migración falló
alembic history

# 2. Deshacer esa migración
alembic downgrade [revision_anterior]

# 3. Editar manualmente el archivo de migración para corregir el error
# 4. Aplicar nuevamente
alembic upgrade head
```

---

## 🔒 REGLAS DE ORO PARA ALEMBIC

### ✅ SÍ HACER

1. **Siempre correr `--autogenerate`**
   ```bash
   alembic revision --autogenerate -m "descripcion"
   ```

2. **Revisar SIEMPRE el archivo .py generado** antes de ejecutar
   ```python
   # Si ves algo raro, edítalo manualmente
   ```

3. **Dar nombres descriptivos a las migraciones**
   ```bash
   # ✅ BIEN
   alembic revision --autogenerate -m "semana3_add_contrato_model"

   # ❌ MAL
   alembic revision --autogenerate -m "cambios"
   ```

4. **Aplicar migraciones en orden**
   ```bash
   alembic upgrade head  # Siempre "head" (última versión)
   ```

### ❌ NO HACER

1. **Editar una migración DESPUÉS de aplicarla**
   ```bash
   # ❌ NO HACER ESTO:
   alembic upgrade head
   # ... luego editas el archivo de migración
   alembic upgrade head  # De nuevo
   ```

   **Por qué:** Alembic ya registró que se ejecutó. Editarla no sirve.

   **Qué hacer:**
   ```bash
   alembic downgrade -1  # Deshacer
   # ... editar el archivo
   alembic upgrade head  # Aplicar nuevamente
   ```

2. **Usar `op.execute()` con SQL de `codigoPostgresSQL.txt`**
   ```python
   # ❌ NO:
   op.execute("""
   CREATE TABLE empleado (...)  -- SQL de SQL directo
   """)

   # ✅ SÍ:
   op.create_table('empleado', ...)  # Usar APIs de Alembic
   ```

3. **Olvidar importar el modelo en `alembic/env.py`**
   ```python
   # ❌ Alembic NO vea el modelo:
   # from app.features.auth.usuario.models import Usuario  # Comentado

   # ✅ Alembic VE el modelo:
   from app.features.auth.usuario.models import Usuario  # noqa: F401
   ```

4. **Ejecutar migraciones sin entender qué hacen**
   ```bash
   # ❌ NO:
   alembic upgrade head   # Sin ver qué cambios se aplican

   # ✅ SÍ:
   # 1. Generar migración
   alembic revision --autogenerate -m "descripcion"
   # 2. REVISAR el archivo generado
   cat alembic/versions/xxxx_*.py
   # 3. SI SE VE BIEN, aplicar
   alembic upgrade head
   ```

---

## 📋 CHECKLIST PARA CADA SEMANA

Cuando necesites agregar un nuevo modelo, usa esta checklist:

```
ANTES DE GENERAR LA MIGRACIÓN:
☐ Modelo Python creado en app/features/[modulo]/[submodulo]/models.py
☐ Clase hereda de Base
☐ Usa Mapped + mapped_column (SQLAlchemy 2.0 puro)
☐ Relaciones bien definidas (con TYPE_CHECKING si es cruzado)

REGISTRAR EN ALEMBIC:
☐ Abrir alembic/env.py
☐ Agregar: from app.features... import MiModelo  # noqa: F401
☐ Colocarlo al final de otros imports del mismo tipo

GENERAR MIGRACIÓN:
☐ Terminal: alembic revision --autogenerate -m "semana_X_descripcion"
☐ Ver el archivo generado: alembic/versions/xxx_*.py
☐ Revisar el SQL generado

APLICAR MIGRACIÓN:
☐ Terminal: alembic upgrade head
☐ Ver que dice "Running upgrade xxxxx -> yyyyy"
☐ Terminal: alembic current (debe mostrar la última versión)

VERIFICAR:
☐ psql -U postgres -d rrhh_bolivia
☐ \dt rrhh.*  (ver la tabla creada)
☐ SELECT COUNT(*) FROM rrhh.mi_tabla;
☐ \q (salir)

DOCUMENTACIÓN:
☐ Notar en Informes/SemanaN/ qué se agregó
☐ Guardar cambios con git
```

---

## RESUMEN: LAS 3 COSAS QUE DEBES RECORDAR

### 1. EL FLUJO BÁSICO
```
Editar Modelo Python → Registrar en env.py → alembic revision --autogenerate → REVISAR → alembic upgrade head → VERIFICAR
```

### 2. LOS COMANDOS PRINCIPALES
```bash
# Generar migración (lo más importante)
alembic revision --autogenerate -m "descripción"

# Aplicar cambios a BD
alembic upgrade head

# Ver estado actual
alembic current

# Deshacer (si algo salió mal)
alembic downgrade -1
```

### 3. LAS REGLAS DE ORO
- ✅ Siempre usar `--autogenerate`
- ✅ SIEMPRE revisar el archivo generado
- ✅ Importar modelos en `alembic/env.py`
- ❌ Nunca editar una migración después de aplicarla

---

## 🎓 CONCLUSIÓN

Alembic es tu mejor amigo porque:

1. **Automático:** Detecta cambios sin que escribas SQL
2. **Versionado:** Historial completo de cambios (como Git)
3. **Reversible:** Puedes deshacer cambios si algo sale mal
4. **Documentado:** Cada cambio está en un archivo Python

**En este proyecto:**
- **Semana 1:** Ya aplicada la migración inicial (6a65fa2dd1f5)
- **Semana 2-10:** Cada semana tendrá su propia migración(es)
- **Total esperado:** ~10 migraciones al final del proyecto

¿Preguntas sobre algún paso específico?
