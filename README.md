# Sistema RRHH Bolivia - MVP

Sistema de Recursos Humanos para Bolivia construido con FastAPI, SQLAlchemy 2.0 y PostgreSQL.

## 🚀 Inicio Rápido

### 1. Requisitos previos
- Python 3.12
- PostgreSQL 14+
- Git

### 2. Instalación, creacion de entorno virtual y dependencias

```bash
# Clonar el repositorio (si aplica)
git clone [URL]
cd Control_Asistencia_Personal

# Crear entorno virtual (opcional pero recomendado)
python -m venv venv     # Windows
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate   # Windows

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
# Editar .env con tu configuración de base de datos
```

### 3. Configurar Base de Datos

```bash
# Crear base de datos
psql -U postgres
CREATE DATABASE rrhh_bolivia;

# Ejecutar migraciones
alembic upgrade head
```

### 3.1 🌱 Base de Datos y Población Inicial (Seed)

**IMPORTANTE:** Leer `/scripts/orden_creacion_entidades.md` ANTES de modelar nuevas entidades para respetar la integridad referencial.

#### Paso 1: Poblar datos base (NIVEL 0 - Entidades Fundacionales)

```bash
# Inserta: ci_depto_emision_ref, rol, departamento, decreto_incremento_salarial
python scripts/seed_base_data.py
```

**Qué se popula:**
- ✓ 9 códigos departamentales SEGIP (LP, CB, SC, OR, PT, TJ, CH, BE, PD)
- ✓ 5 roles del sistema (admin, rrhh, supervisor, empleado, consulta)
- ✓ Estructura jerárquica de departamentos (Gerencia General + 4 gerencias)
- ✓ Decreto de incremento salarial 2024 con tramos diferenciados

#### Paso 2: Datos operacionales (Opcional - Future Levels)

```bash
# NIVEL 1: cargos y parámetros de impuesto
# python scripts/seed_nivel_1.py  (próxima semana)

# NIVEL 2: empleados de ejemplo
# python scripts/seed_nivel_2.py  (próxima semana)

# NIVEL 3: usuarios, contratos, horarios
# python scripts/seed_nivel_3.py  (próxima semana)
```

#### Validar población de datos

```bash
# Ejecutar migraciones y seed en orden
alembic upgrade head && python scripts/seed_base_data.py

# Verificar en psql
psql -U postgres -d rrhh_bolivia -c "
SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'rrhh';
SELECT COUNT(*) as complementos FROM rrhh.complemento_dep;
SELECT COUNT(*) as roles FROM rrhh.rol;
SELECT COUNT(*) as departamentos FROM rrhh.departamento;
SELECT COUNT(*) as decretos FROM rrhh.decreto_incremento_salarial;
"
```

### 4. Ejecutar la aplicación

```bash
uvicorn app.main:app --reload --port 8000
```


### 5. Acceder a la documentación
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 📂 Estructura del Proyecto

```
v13/
├── app/
│   ├── core/           # Configuración y database
│   ├── db/             # Base para modelos
│   ├── features/       # Módulos por dominio
│   │   ├── auth/       # Autenticación (Rol, Usuario)
│   │   ├── employees/  # Empleados (Departamento, Cargo, Empleado)
│   │   ├── contracts/  # Contratos y ajustes salariales
│   │   ├── attendance/ # Asistencia y marcaciones
│   │   └── reports/    # Reportes
│   └── main.py         # Entry point
├── alembic/            # Migraciones
├── scripts/            # Scripts de utilidad
├── tests/              # Pruebas
├── Informes/           # Documentación por semana
└── InformacionContexto/# Archivos de referencia
```

## Usuario Admin por defecto

Después de ejecutar el seed:
- **Username:** admin
- **Password:** admin123
- **Rol:** admin

⚠️ **IMPORTANTE:** Cambiar la contraseña en producción

**NOTA:** El email del usuario se obtiene desde `usuario.empleado.email` (campo en tabla `empleado`), no desde `usuario` directamente.

## 📋 Progreso del Proyecto

- ✅ **Semana 1:** Estructura base + modelos iniciales
- ✅ **Semana 2:** Módulo Auth (Rol + Usuario)
- ✅ **Semana 3:** Módulo Employees completo
- ✅ **Semana 4:** Módulo Contracts
- ✅ **Semana 5:** Módulo Marcaciones + Upload Excel
- ✅ **Semana 6:** Módulo Asistencia Diaria + Worker
- ✅ **Semana 7:** Feriados + Cumpleaños + Justificaciones
- ⏳ **Semana 8:** Módulo Reports
- ⏳ **Semana 9:** JWT + Tests
- ⏳ **Semana 10:** Pulido Final

## 🛠️ Stack Tecnológico

- **Framework:** FastAPI
- **ORM:** SQLAlchemy 2.0 (Mapped + mapped_column)
- **Base de Datos:** PostgreSQL 14+
- **Migraciones:** Alembic
- **Validación:** Pydantic v2
- **Auth:** bcrypt (JWT en Semana 9)
- **Excel:** Pandas + openpyxl
- **Scheduler:** APScheduler

## 📚 Documentación

Cada semana tiene su propia documentación en `Informes/SemanaN/resumen.md` con:
- Lo que se construyó
- Comandos ejecutados
- Decisiones técnicas
- Qué viene después

## 🧪 Pruebas

```bash
# Ejecutar pruebas (Semana 9)
pytest

# Ver cobertura
pytest --cov=app tests/
```

## 📖 Convenciones de código

1. Modelos en SQLAlchemy 2.0 puro (Mapped + mapped_column)
2. Toda lógica de negocio en services.py
3. Routers solo para endpoints REST
4. Alembic SIEMPRE con --autogenerate
5. Comentarios y docstrings en español
6. NUNCA usar SQLModel

## 🔄 Workflow de desarrollo

1. Crear/modificar modelos en `models.py`
2. Actualizar `alembic/env.py` con imports
3. Generar migración: `alembic revision --autogenerate -m "descripcion"`
4. Revisar y aplicar: `alembic upgrade head`
5. Crear schemas Pydantic
6. Implementar lógica en services
7. Crear endpoints en routers
8. Activar routers en `main.py`
9. Probar en /docs

## 🐛 Troubleshooting

### No se puede conectar a PostgreSQL
- Verificar que PostgreSQL esté corriendo
- Revisar DATABASE_URL en .env
- Verificar puerto (por defecto 5432)

### Alembic no detecta cambios
- Verificar que el modelo esté importado en `alembic/env.py`
- Verificar que el modelo herede de Base
- Revisar que las columnas usen `Mapped` y `mapped_column`

### Error de importación circular
- Usar TYPE_CHECKING para imports de tipos
- Importar modelos en strings en relationships
