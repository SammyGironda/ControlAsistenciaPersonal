# SEMANA 1 - Informe de Progreso

## Objetivo
Crear la estructura base del proyecto, archivos core y modelos iniciales.

## Archivos Creados

### Core
- `app/core/config.py` - Configuración con pydantic-settings
- `app/core/database.py` - Conexión SQLAlchemy 2.0 + search_path automático
- `app/db/base.py` - Base declarativa + registro de modelos para Alembic

### Modelos (SQLAlchemy 2.0 puro)
| Modelo | Archivo | Descripción |
|--------|---------|-------------|
| Rol | `app/features/auth/rol/models.py` | Roles del sistema (admin, rrhh, consulta) |
| ComplementoDep | `app/features/employees/departamento/models.py` | Códigos SEGIP (LP, SC, CB, etc.) |
| Departamento | `app/features/employees/departamento/models.py` | Estructura organizacional jerárquica |
| Cargo | `app/features/employees/cargo/models.py` | Puestos de trabajo |
| Empleado | `app/features/employees/empleado/models.py` | Datos personales y laborales |

### Utilidades
- `app/features/common/utils.py` - Funciones auxiliares
- `app/main.py` - FastAPI con endpoints de salud
- `requirements.txt` - Dependencias actualizadas

## ENUMs Definidos (en Python)
- `GeneroEnum`: masculino, femenino, otro
- `EstadoEmpleadoEnum`: activo, baja, suspendido

## Estructura de Carpetas
```
app/
├── __init__.py
├── main.py
├── core/
│   ├── __init__.py
│   ├── config.py
│   └── database.py
├── db/
│   ├── __init__.py
│   └── base.py
└── features/
    ├── common/utils.py
    ├── auth/rol/
    ├── auth/usuario/
    ├── employees/departamento/
    ├── employees/cargo/
    ├── employees/empleado/
    ├── contracts/...
    ├── attendance/...
    └── reports/...
```

## Pendiente (Semana 1 - Parte 2)
- [ ] Instalar dependencias: `pip install -r requirements.txt`
- [ ] Inicializar Alembic: `alembic init alembic`
- [ ] Configurar `alembic.ini` y `env.py`
- [ ] Crear schema `rrhh` en PostgreSQL
- [ ] Generar migración: `alembic revision --autogenerate`
- [ ] Ejecutar migración: `alembic upgrade head`

## Notas Técnicas
- Todos los modelos usan `Mapped` + `mapped_column` (SQLAlchemy 2.0)
- El schema `rrhh` se configura automáticamente via `search_path`
- Los ENUMs se definen como Python Enum + `native_enum=False` para portabilidad
- Relaciones configuradas pero comentadas hasta activar modelos relacionados
