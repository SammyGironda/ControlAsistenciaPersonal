# 📖 Guía de Uso - Sistema de Poblado de Datos Base

## 📂 Archivos Incluidos

```
/scripts/
├── seed_base_data.py               ← Script de NIVEL 0 (entidades base)
├── orden_creacion_entidades.md     ← Arquitectura de dependencias (LÉELO PRIMERO)
├── GUIA_USO.md                     ← Este archivo
└── [próximos]
    ├── seed_nivel_1.py             (cargos, parámetros impuesto)
    ├── seed_nivel_2.py             (empleados)
    └── seed_nivel_3.py             (usuarios, contratos, horarios)
```

---

## 🚀 Inicio Rápido (5 minutos)

### 1. Prerequisitos
```bash
# Verificar Python 3.12+
python --version

# Verificar PostgreSQL
psql --version

# Instalar dependencias
pip install -r requirements.txt
```

### 2. Crear Base de Datos
```bash
# Conectar a PostgreSQL
psql -U postgres

# Crear base de datos y schema
CREATE DATABASE rrhh_bolivia;
\c rrhh_bolivia

-- Crear schema rrhh
CREATE SCHEMA IF NOT EXISTS rrhh;
GRANT ALL PRIVILEGES ON SCHEMA rrhh TO postgres;
EXIT;
```

### 3. Ejecutar Migraciones
```bash
# Desde la raíz del proyecto
alembic upgrade head

# Verificar que las tablas se crearon
psql -U postgres -d rrhh_bolivia -c "\dt rrhh.*"
```

### 4. Poblar Datos Base (NIVEL 0)
```bash
# Desde la raíz del proyecto
python scripts/seed_base_data.py

# Output esperado:
# =======================================================================
# SEED NIVEL 0 - DATOS BASE FUNDACIONALES
# =======================================================================
# [NIVEL 0] → Insertando catálogo SEGIP (ci_depto_emision_ref)...
#   ✓ 9 departamentos SEGIP insertados exitosamente.
# [NIVEL 0] → Insertando roles del sistema...
#   ✓ 5 roles insertados exitosamente.
# [NIVEL 0] → Insertando estructura departamental organizacional...
#   ✓ Gerencia General (raíz) creada con ID=1
#   ✓ 4 gerencias de nivel 1 creadas
#   ✓ 2 áreas bajo RRHH creadas
#   ✓ Estructura departamental completada exitosamente.
# [NIVEL 0] → Insertando decreto de incremento salarial...
#   ✓ Decreto DS 4984/2024 (SMN: 2500 Bs) creado
#   ✓ 3 tramos de decreto insertados exitosamente
#     • Tramo 1: Hasta 2500 Bs → 5%
#     • Tramo 2: 2501 a 5000 Bs → 3%
#     • Tramo 3: Más de 5000 Bs → 1%
# ✅ SEED NIVEL 0 COMPLETADO CON ÉXITO
```

### 5. Validar Base de Datos
```bash
# Conectar a la base de datos
psql -U postgres -d rrhh_bolivia

# Consultas de validación
SELECT COUNT(*) as departamentos_segip FROM rrhh.complemento_dep;
SELECT COUNT(*) as roles FROM rrhh.rol;
SELECT COUNT(*) as departamentos FROM rrhh.departamento;
SELECT COUNT(*) as decretos FROM rrhh.decreto_incremento_salarial;

-- Exit
\q
```

---

## ✨ Qué Hace Cada Función

### `seed_base_data.py`

#### 1. `seed_ci_depto_emision_ref(db)`
**Inserta:** Códigos de departamento del SEGIP de Bolivia

| Código | Departamento | Activo |
|--------|--------------|--------|
| LP | La Paz | ✓ |
| CB | Cochabamba | ✓ |
| SC | Santa Cruz | ✓ |
| OR | Oruro | ✓ |
| PT | Potosí | ✓ |
| TJ | Tarija | ✓ |
| CH | Chuquisaca | ✓ |
| BE | Beni | ✓ |
| PD | Pando | ✓ |

**Uso:** Validar y almacenar códigos de emisión de CI en registros de empleados.

---

#### 2. `seed_roles(db)`
**Inserta:** Roles de acceso del sistema

| Rol | Descripción | Activo |
|-----|-------------|--------|
| admin | Acceso total al sistema | ✓ |
| rrhh | Gestión de empleados y asistencia | ✓ |
| supervisor | Aprueba permisos y justificaciones | ✓ |
| empleado | Consulta su propia información | ✓ |
| consulta | Solo lectura de reportes | ✓ |

**Uso:** Controlar permisos de usuarios en la aplicación.

---

#### 3. `seed_departamentos(db)`
**Inserta:** Estructura organizacional jerárquica

```
Gerencia General (id=1, id_padre=NULL)
├─ Gerencia RRHH (id=2, id_padre=1)
│  ├─ Área Nóminas (id=5, id_padre=2)
│  └─ Área Selección (id=6, id_padre=2)
├─ Gerencia Administrativa (id=3, id_padre=1)
├─ Gerencia Comercial (id=4, id_padre=1)
└─ Gerencia de Sistemas (id=4, id_padre=1)
```

**Uso:** Organizar empleados en estructura jerárquica para reportes y delegación.

---

#### 4. `seed_decreto_incremento_salarial(db)`
**Inserta:** Decreto Supremo 4984 / 2024 de Bolivia

```
Decreto: DS 4984 / 2024
Nuevo SMN: 2500 Bs
Fecha Vigencia: 1 de mayo de 2024

Tramos de Incremento:
1. Hasta 2500 Bs → 5% de incremento
2. De 2501 a 5000 Bs → 3% de incremento
3. Más de 5000 Bs → 1% de incremento
```

**Uso:** Calcular incrementos salariales anuales automáticamente según rango salarial.

---

## 🔍 Verificación de Datos Poblados

### Desde PostgreSQL CLI

```bash
psql -U postgres -d rrhh_bolivia

-- Ver complementos (SEGIP)
\c rrhh
SELECT codigo, nombre_departamento, activo FROM complemento_dep ORDER BY codigo;

-- Ver roles
SELECT id, nombre, descripcion, activo FROM rol ORDER BY id;

-- Ver departamentos (estructura jerárquica)
SELECT id, nombre, codigo, id_padre, activo FROM departamento ORDER BY id_padre NULLS FIRST, id;

-- Ver decreto
SELECT id, anio, nuevo_smn, fecha_vigencia, referencia_decreto FROM decreto_incremento_salarial;

-- Ver tramos del decreto
SELECT cd.orden, cd.salario_desde, cd.salario_hasta, cd.porcentaje_incremento 
FROM condicion_decreto cd
ORDER BY cd.orden;

\q
```

### Desde Python

```python
from app.core.database import SessionLocal
from app.features.employees.departamento.models import ComplementoDep, Departamento
from app.features.auth.rol.models import Rol
from app.features.contracts.ajuste_salarial.models import DecretoIncrementoSalarial

db = SessionLocal()

# Verificar complementos
complementos = db.query(ComplementoDep).all()
print(f"Total complementos SEGIP: {len(complementos)}")

# Verificar roles
roles = db.query(Rol).all()
print(f"Roles del sistema: {[r.nombre for r in roles]}")

# Verificar departamentos
depto_raiz = db.query(Departamento).filter_by(id_padre=None).first()
print(f"Departamento raíz: {depto_raiz.nombre}")

# Verificar decreto
decreto = db.query(DecretoIncrementoSalarial).filter_by(anio=2024).first()
print(f"Decreto 2024: {decreto.referencia_decreto}, SMN: {decreto.nuevo_smn}")

db.close()
```

---

## ⚠️ Solución de Problemas

### Error: `ModuleNotFoundError: No module named 'app'`

**Problema:** El script no encuentra el módulo `app`.

**Solución:**
```bash
# Asegúrate de:
# 1. Estar en la raíz del proyecto
$ pwd  # Debe ser /d/DOCUMENTOS/Desktop/BLUENET/02PROYECTO/v13

# 2. El sys.path está bien en seed_base_data.py
# Línea 16: sys.path.insert(0, str(Path(__file__).parent.parent))

# 3. Si aún falla, ejecuta desde la raíz
cd /d/DOCUMENTOS/Desktop/BLUENET/02PROYECTO/v13
python scripts/seed_base_data.py
```

---

### Error: `psycopg2.OperationalError: could not translate host name`

**Problema:** No puede conectar a PostgreSQL.

**Solución:**
```bash
# 1. Verificar que PostgreSQL esté corriendo
# Windows:
Get-Service | findstr -i postgres

# Linux/Mac:
ps aux | grep postgres

# 2. Verificar DATABASE_URL en .env
cat .env | grep DATABASE_URL

# 3. Verificar puerto (por defecto 5432)
psql -U postgres -h localhost -p 5432 -c "SELECT version();"
```

---

### Error: `IntegrityError: foreign key violation`

**Problema:** No se ejecutaron las migraciones correctamente.

**Solución:**
```bash
# 1. Verificar que las tablas existen
psql -U postgres -d rrhh_bolivia -c "\dt rrhh.*"

# 2. Si falta algo, ejecutar migraciones nuevamente
alembic upgrade head

# 3. Intentar seed nuevamente
python scripts/seed_base_data.py
```

---

### Error: `UNIQUE constraint failed: rol.nombre`

**Problema:** Los datos ya están poblados y se ejecutó el script dos veces.

**Solución:**
```bash
# Los datos ya existen, es seguro ignorar este error.
# El script valida con .first() antes de insertar (idempotente).

# Si necesitas resetear:
psql -U postgres -d rrhh_bolivia
DROP SCHEMA rrhh CASCADE;
CREATE SCHEMA rrhh;
\q

# Luego ejecutar migraciones y seed nuevamente
alembic upgrade head
python scripts/seed_base_data.py
```

---

## 🔄 Workflow Típico

### Primera vez (Setup inicial)

```bash
# 1. Crear BD
psql -U postgres -c "CREATE DATABASE rrhh_bolivia;"

# 2. Ejecutar migraciones
alembic upgrade head

# 3. Poblar datos base
python scripts/seed_base_data.py

# 4. Validar
psql -U postgres -d rrhh_bolivia -c "SELECT COUNT(*) FROM rrhh.rol;"
```

### Después (Desarrollo)

```bash
# Si creo nuevo modelo:
# 1. Actualizar models.py
# 2. Generar migración
alembic revision --autogenerate -m "descripción"

# 3. Revisar la migración
cat alembic/versions/[archivo].py

# 4. Aplicar
alembic upgrade head

# 5. Si necesito seed de nuevo:
python scripts/seed_base_data.py  # Idempotente, sin problema
```

---

## 📊 Estructura de Datos Poblada

```
┌─────────────────────────────────────────┐
│      SEED BASE DATA (NIVEL 0)           │
└─────────────────────────────────────────┘

┌─ ComplementoDep (ci_depto_emision_ref)
│  LP, CB, SC, OR, PT, TJ, CH, BE, PD
│
├─ Rol
│  admin, rrhh, supervisor, empleado, consulta
│
├─ Departamento (jerárquico)
│  GG (raíz)
│  ├─ RRHH
│  │  ├─ RRHH-NOM
│  │  └─ RRHH-SEL
│  ├─ ADM
│  ├─ COM
│  └─ SIS
│
└─ DecretoIncrementoSalarial (2024)
   ├─ CondicionDecreto (Tramo 1: 0-2500 Bs → 5%)
   ├─ CondicionDecreto (Tramo 2: 2501-5000 Bs → 3%)
   └─ CondicionDecreto (Tramo 3: 5000+ Bs → 1%)

↓ Próximas ejecutar en orden:
├─ seed_nivel_1.py (Cargo, ParametroImpuesto)
├─ seed_nivel_2.py (Empleado)
└─ seed_nivel_3.py (Usuario, Contrato, Horario, AsignacionHorario)
```

---

## 📚 Referencias

- **Arquitectura:** Ver `/scripts/orden_creacion_entidades.md`
- **Documentación Alembic:** https://alembic.sqlalchemy.org/
- **SQLAlchemy 2.0:** https://docs.sqlalchemy.org/20/
- **PostgreSQL:** https://www.postgresql.org/docs/

---

## 💡 Consejos

1. **Siempre leer `orden_creacion_entidades.md`** antes de agregar nuevas entidades
2. **Los seeds son idempotentes:** Se pueden ejecutar múltiples veces sin problema
3. **Validar con SQL:** Después de ejecutar seed, verificar en la BD
4. **Mantener comentarios:** Cada seed debe documentar qué inserta y por qué
5. **Usar transacciones:** Todo o nada, sin datos inconsistentes

---

**Versión:** 1.0  
**Última actualización:** 2026-04-14  
**Autor:** Sistema RRHH Bolivia MVP
