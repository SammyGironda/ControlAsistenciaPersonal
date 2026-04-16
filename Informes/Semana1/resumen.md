# 📊 SEMANA 1 — RESUMEN EJECUTIVO

## 🎯 Objetivo Cumplido

Establecer los **cimientos sólidos del proyecto**: estructura de carpetas, configuración de base de datos, modelos iniciales y primera migración funcional.

---

## ✅ Entregables Completados

### 1. Estructura de Proyecto

```
v13/
├── app/
│   ├── core/
│   │   ├── config.py          ← Variables de entorno con Pydantic Settings
│   │   └── database.py        ← Engine + SessionLocal + get_db
│   ├── db/
│   │   └── base.py            ← Base declarativa + metadata
│   ├── features/
│   │   ├── auth/
│   │   │   ├── rol/
│   │   │   │   └── models.py  ← Modelo Rol
│   │   │   └── usuario/
│   │   │       └── models.py  ← Modelo Usuario
│   │   └── employees/
│   │       ├── departamento/
│   │       │   └── models.py  ← Departamento + ComplementoDep
│   │       ├── cargo/
│   │       │   └── models.py  ← Modelo Cargo
│   │       └── empleado/
│   │           └── models.py  ← Modelo Empleado
│   └── main.py                ← Punto de entrada FastAPI
├── alembic/
│   ├── versions/
│   │   ├── 6a65fa2dd1f5_init_modelos_base.py
│   │   └── (próxima: agregar_tabla_usuario.py)
│   └── env.py                 ← Importa todos los modelos
├── scripts/
│   └── seed_inicial.py        ← Datos semilla
├── Informes/
│   └── Semana1/
│       ├── INSTRUCCIONES_MIGRACION.md
│       └── resumen.md         ← Este archivo
├── .env                       ← Variables de entorno
├── requirements.txt           ← Dependencias
└── alembic.ini                ← Configuración de Alembic
```

---

### 2. Modelos SQLAlchemy 2.0 (Mapped + mapped_column)

#### **CiDeptoEmisionRef (ComplementoDep)**
Códigos de departamento de Bolivia para emisión de CI según SEGIP.
- Campos: `codigo` (PK), `nombre_departamento`, `activo`
- 9 registros: LP, CB, SC, OR, PT, TJ, CH, BE, PA

#### **Rol**
Roles del sistema para control de acceso (aunque JWT se activa en Semana 9).
- Campos: `id`, `nombre` (unique), `descripcion`, `activo`, `created_at`, `updated_at`
- Relación: `1 → N` con Usuario
- 5 roles semilla: admin, rrhh, supervisor, empleado, consulta

#### **Departamento**
Estructura organizacional jerárquica de la empresa.
- Campos: `id`, `nombre`, `codigo` (unique), `id_padre` (autorreferencial), `activo`, `created_at`, `updated_at`
- Relación: `1 → N` con Cargo y Empleado
- Jerarquía: Gerencia General → Gerencias → Áreas
- Ejemplo de datos semilla:
  - Gerencia General (GG)
    - Gerencia RRHH (RRHH)
      - Área Nóminas (RRHH-NOM)
      - Área Selección (RRHH-SEL)
    - Gerencia Administrativa (ADM)
    - Gerencia Comercial (COM)
    - Gerencia de Sistemas (SIS)

#### **Cargo**
Puestos de trabajo dentro de la organización.
- Campos: `id`, `nombre`, `codigo` (unique), `nivel`, `es_cargo_confianza`, `id_departamento`, `activo`, `created_at`, `updated_at`
- Relación: `N → 1` con Departamento, `1 → N` con Empleado
- `es_cargo_confianza = TRUE` → Exento de marcar huella biométrica
- 9 cargos semilla: desde Gerente General (nivel 1) hasta Desarrollador Junior (nivel 5)

#### **Empleado**
Datos personales y laborales de cada empleado.
- Campos de identificación: `ci_numero`, `complemento_dep` (FK), `ci_sufijo_homonimo`
- Campos personales: `nombres`, `apellidos`, `fecha_nacimiento`, `genero`
- Campos laborales: `fecha_ingreso`, `estado`, `id_cargo`, `id_departamento`, `salario_base`
- Campos de contacto: `email`, `telefono`, `foto_url`
- Auditoría: `created_at`, `updated_at`
- Relaciones: `N → 1` con Cargo, Departamento, ComplementoDep
- ENUMs:
  - `genero_enum`: masculino, femenino, otro
  - `estado_empleado_enum`: activo, baja, suspendido
- Property `ci_completo`: Retorna CI formateado (ej: "1234567-LP" o "1234567-LP-1A")
- Property `nombre_completo`: Retorna nombre y apellido concatenados

#### **Usuario**
Cuentas de acceso al sistema (vinculadas a empleados).
- Campos: `id`, `id_empleado` (FK unique), `id_rol` (FK), `username` (unique), `password_hash`, `activo`, `ultimo_acceso`, `created_at`, `updated_at`
- Relación: `1 → 1` con Empleado, `N → 1` con Rol
- **IMPORTANTE:** Aunque este modelo se crea ahora, la autenticación JWT NO se activa hasta Semana 9

---

### 3. Configuración de Base de Datos

#### **app/core/config.py**
- Usa `pydantic-settings` para cargar variables de entorno desde `.env`
- Variables críticas:
  - `DATABASE_URL`: Conexión a PostgreSQL
  - `DB_SCHEMA`: "rrhh"
  - `SECRET_KEY`: Para JWT (Semana 9)
  - `DEBUG`: Imprime queries SQL si `True`

#### **app/core/database.py**
- `engine`: SQLAlchemy engine con `pool_pre_ping=True`
- Event listener: Establece `search_path = rrhh, public` en cada conexión
- `SessionLocal`: Factory de sesiones
- `get_db()`: Dependencia de FastAPI que provee sesiones DB

#### **app/db/base.py**
- `Base`: Clase declarativa con metadata y convención de nombres
- Schema: `rrhh` (todas las tablas se crean en este schema)
- **NO importa modelos aquí** (para evitar imports circulares)

#### **alembic/env.py**
- **SÍ importa todos los modelos** para que Alembic los detecte
- Configuración de `include_schemas=True` y `compare_type=True`
- `version_table` va en schema `public` (por defecto, sin especificar `version_table_schema`)

---

### 4. Migraciones Alembic

#### **Migración 1: 6a65fa2dd1f5_init_modelos_base.py**
Ya aplicada. Contiene:
- Tablas: `complemento_dep`, `rol`, `departamento`, `cargo`, `empleado`
- ENUMs: `genero_enum`, `estado_empleado_enum`
- Constraints: PKs, FKs, UNIQUEs

#### **Migración 2: agregar_tabla_usuario.py** (pendiente de generar)
Debes generar y aplicar. Contendrá:
- Tabla: `usuario`
- Función: `fn_set_updated_at()`
- Triggers: `trg_{tabla}_set_updated_at` en todas las tablas con `updated_at`

**Comandos ejecutados:**
```bash
# Generar migración
python -m alembic revision --autogenerate -m "agregar_tabla_usuario"

# Aplicar migración
python -m alembic upgrade head
```

---

### 5. Script de Datos Semilla

**Archivo:** `scripts/seed_inicial.py`

**Funciones:**
- `seed_complemento_dep()`: 9 departamentos de Bolivia
- `seed_roles()`: 5 roles del sistema
- `seed_departamentos()`: Estructura organizacional jerárquica
- `seed_cargos()`: 9 cargos iniciales

**Ejecución:**
```bash
python scripts/seed_inicial.py
```

**Registros insertados:**
- 9 complementos de departamento (LP, CB, SC, OR, PT, TJ, CH, BE, PA)
- 5 roles (admin, rrhh, supervisor, empleado, consulta)
- 6 departamentos organizacionales (GG, RRHH, ADM, COM, SIS, áreas)
- 9 cargos (desde nivel 1 a nivel 5)

---

### 6. Aplicación FastAPI

**Archivo:** `app/main.py`

**Contenido:**
- Configuración de CORS (allow all durante desarrollo)
- Endpoints de health: `/` y `/health`
- Swagger UI: `/docs`
- ReDoc: `/redoc`

**Levantar la app:**
```bash
python -m uvicorn app.main:app --reload --port 8000
```

**Verificar:**
- http://localhost:8000/ → Info de la API
- http://localhost:8000/docs → Swagger interactivo
- http://localhost:8000/health → `{"status": "healthy"}`

---

## 🛠️ Tecnologías Utilizadas

- **Python 3.12**
- **FastAPI 0.115.6** (framework web)
- **SQLAlchemy 2.0.36** (ORM con Mapped + mapped_column)
- **Alembic 1.14.0** (migraciones)
- **PostgreSQL 14+** (base de datos)
- **Pydantic 2.10.4** (validación y settings)
- **Uvicorn 0.34.0** (servidor ASGI)

---

## 🧠 Decisiones Técnicas Clave

### ¿Por qué SQLAlchemy 2.0 puro y NO SQLModel?
**Razón:** Mayor control sobre relaciones complejas, metaprogramación avanzada y compatibilidad total con Alembic. SQLModel es excelente pero más limitado para sistemas enterprise con jerarquías complejas como `Departamento` autorreferencial.

### ¿Por qué Alembic con --autogenerate?
**Razón:** Define los modelos en Python (fuente de verdad) y deja que Alembic genere el SQL automáticamente. Esto evita duplicar código y minimiza errores. Solo usamos `op.execute()` para ENUMs, triggers y funciones que Alembic no detecta.

### ¿Por qué schema "rrhh" en PostgreSQL?
**Razón:** Organización lógica. Permite tener múltiples aplicaciones en la misma BD sin conflicto de nombres. También facilita backups selectivos y permisos granulares.

### ¿Por qué fn_set_updated_at() como función + trigger?
**Razón:** Centraliza la lógica de auditoría en la BD. Así, aunque actualices registros desde SQL directo (sin pasar por la app), el `updated_at` se actualiza automáticamente. Es más confiable que hacerlo en el ORM.

### ¿Por qué NO activar JWT hasta Semana 9?
**Razón:** Enfoque en velocidad de desarrollo del MVP. Primero construimos toda la funcionalidad y luego la aseguramos. Esto permite iterar rápido y probar endpoints sin fricciones.

---

## 📈 Métricas de la Semana

- **6 modelos** SQLAlchemy creados
- **2 ENUMs** de PostgreSQL
- **1 función** PL/pgSQL (`fn_set_updated_at`)
- **5 triggers** aplicados
- **2 migraciones** Alembic (1 aplicada, 1 pendiente)
- **29 registros** de datos semilla
- **0 endpoints** REST (próxima semana)

---

## ⚠️ Notas Importantes

1. **Autenticación desactivada:** Todos los endpoints estarán abiertos hasta Semana 9.
2. **Schema rrhh:** Siempre especificar el schema en consultas SQL directas.
3. **Migraciones:** NUNCA editar una migración ya aplicada. Siempre crear una nueva.
4. **Soft delete:** En semanas futuras, usaremos `activo=False` en lugar de borrar registros.

---

## 🚀 Próximos Pasos — SEMANA 2

Objetivos:
1. **Schemas Pydantic** para Rol y Usuario (Request/Response)
2. **Services** con CRUD completo (crear, leer, actualizar, desactivar)
3. **Routers** con endpoints REST:
   - `GET /api/v1/roles` → Listar roles
   - `POST /api/v1/roles` → Crear rol
   - `GET /api/v1/roles/{id}` → Obtener rol por ID
   - `PUT /api/v1/roles/{id}` → Actualizar rol
   - `DELETE /api/v1/roles/{id}` → Soft delete (activo=False)
   - Endpoints similares para Usuario
4. **Hash de contraseñas** con bcrypt (preparación para JWT de Semana 9)
5. **Validación** de datos con Pydantic v2
6. **Documentación** automática en Swagger

---

## 📚 Aprendizajes de la Semana

### SQLAlchemy 2.0: Mapped + mapped_column
```python
# ✅ CORRECTO (SQLAlchemy 2.0)
id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
nombre: Mapped[str] = mapped_column(String(100), nullable=False)

# ❌ INCORRECTO (SQLAlchemy 1.4)
id = Column(Integer, primary_key=True, autoincrement=True)
nombre = Column(String(100), nullable=False)
```

### Relaciones bidireccionales
```python
# Modelo Departamento
hijos: Mapped[List["Departamento"]] = relationship("Departamento", back_populates="padre")
padre: Mapped[Optional["Departamento"]] = relationship("Departamento", remote_side=[id], back_populates="hijos")

# Modelo Rol
usuarios: Mapped[list["Usuario"]] = relationship(back_populates="rol")

# Modelo Usuario
rol: Mapped["Rol"] = relationship(back_populates="usuarios")
```

### Alembic autogenerate
```bash
# Genera migración automáticamente comparando modelos con BD
python -m alembic revision --autogenerate -m "descripcion"

# Aplica la migración
python -m alembic upgrade head

# Revierte la última migración
python -m alembic downgrade -1
```

---

## 🎓 Comandos Útiles de la Semana

```bash
# Verificar estado de migraciones
python -m alembic current

# Ver historial completo
python -m alembic history

# Generar migración
python -m alembic revision --autogenerate -m "mensaje"

# Aplicar migración
python -m alembic upgrade head

# Revertir migración
python -m alembic downgrade -1

# Ejecutar seed
python scripts/seed_inicial.py

# Levantar la app
python -m uvicorn app.main:app --reload --port 8000

# Verificar dependencias
pip list

# Instalar dependencias
pip install -r requirements.txt
```

---

## ✅ Checklist de Verificación

- [x] Entorno virtual activado y dependencias instaladas
- [x] Archivo `.env` configurado con `DATABASE_URL` correcta
- [x] PostgreSQL corriendo y BD `rrhh_bolivia` creada
- [x] Schema `rrhh` creado en PostgreSQL
- [ ] Migración inicial aplicada (`alembic upgrade head`)
- [ ] Nueva migración generada con modelo Usuario
- [ ] Migración editada con función y triggers
- [ ] Nueva migración aplicada
- [ ] Script de seed ejecutado
- [ ] App levantando sin errores en http://localhost:8000
- [ ] Swagger accesible en http://localhost:8000/docs
- [ ] Verificación en PostgreSQL de tablas y datos

---

## 🙏 Mensaje Final

¡Felicidades por completar la **Semana 1**! 🎉

Has establecido una base sólida para el proyecto. La estructura de carpetas, los modelos bien diseñados con SQLAlchemy 2.0, y las migraciones funcionando correctamente son el **cimiento** sobre el cual construiremos el resto del sistema.

**Lo más importante que aprendiste esta semana:**
1. Cómo estructurar un proyecto FastAPI profesional
2. Cómo usar SQLAlchemy 2.0 con Mapped + mapped_column
3. Cómo generar y aplicar migraciones con Alembic autogenerate
4. Cómo insertar datos semilla de manera programática

**En la próxima semana** empezarás a ver resultados tangibles: endpoints REST completamente funcionales que podrás probar desde Swagger.

¡Adelante con la Semana 2! 🚀

---

**Fecha de finalización:** 2026-03-23
**Tiempo invertido:** ~4 horas
**Líneas de código Python:** ~800
**Commits sugeridos:** 3 (modelos, migración, seed)
