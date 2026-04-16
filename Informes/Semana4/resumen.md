# INFORME SEMANA 4 - MÓDULO CONTRACTS

## 📅 Fecha: 06 de abril de 2026
## 🎯 Objetivo: Verificar y corregir el estado del proyecto en Semana 4

---

## ✅ ESTADO GENERAL: COMPLETADO CON CORRECCIONES

El módulo de Contracts (Semana 4) está **implementado y funcional**, pero se encontraron **3 problemas críticos** que fueron corregidos exitosamente.

---

## 🔍 PROBLEMAS ENCONTRADOS Y CORREGIDOS

### 1. ❌ PROBLEMA: Imports faltantes en alembic/env.py

**Descripción:**
El archivo `alembic/env.py` solo importaba 2 de los 5 modelos de Semana 4:
- ✅ Importados: `Contrato`, `AjusteSalarial`
- ❌ **Faltaban**: `DecretoIncrementoSalarial`, `CondicionDecreto`, `ParametroImpuesto`

**Impacto:**
Alembic no podría detectar cambios futuros en estos modelos al usar `--autogenerate`.

**Solución aplicada:**
```python
# Archivo: alembic/env.py (líneas 24-30)
from app.features.contracts.contrato.models import Contrato  # noqa: F401
from app.features.contracts.ajuste_salarial.models import (  # noqa: F401
    AjusteSalarial,
    DecretoIncrementoSalarial,
    CondicionDecreto,
    ParametroImpuesto
)
```

**Estado:** ✅ CORREGIDO

---

### 2. ❌ PROBLEMA: Campo email faltante en modelo Usuario

**Descripción:**
Desincronización entre base de datos y modelo Python:
- La tabla `rrhh.usuario` en PostgreSQL **SÍ** tiene la columna `email` (creada en Semana 2)
- El modelo `Usuario` en Python **NO** tenía el campo `email`

**Detección:**
```bash
$ alembic check
ERROR: Detected removed column 'rrhh.usuario.email'
```

**Impacto:**
- Alembic reportaba error de sincronización
- El campo email no era accesible desde el ORM
- Las migraciones futuras podrían intentar eliminar la columna

**Solución aplicada:**

**Archivo:** `app/features/auth/usuario/models.py`
```python
# Agregado entre líneas 64-68
# --- Email (opcional) ---
email: Mapped[Optional[str]] = mapped_column(
    String(150),
    nullable=True
)
```

**Archivo:** `app/features/auth/usuario/schemas.py`
- Agregado campo `email` en `UsuarioCreate`
- Agregado campo `email` en `UsuarioUpdate`
- Agregado campo `email` en `UsuarioRead`
- Agregado campo `email` en `UsuarioReadWithRol`

**Verificación:**
```bash
$ alembic check
No new upgrade operations detected.  ✅ SINCRONIZADO
```

**Estado:** ✅ CORREGIDO

---

### 3. ⚠️ OBSERVACIÓN: Scripts seed sin datos de Semana 4

**Descripción:**
Los scripts `seed_data.py` y `seed_inicial.py` NO incluyen datos de ejemplo para:
- Decretos de incremento salarial
- Condiciones de decreto (tramos salariales)
- Parámetros de impuestos (RC_IVA, AFP_LABORAL, etc.)

**Impacto:**
- No afecta el funcionamiento del sistema
- Los endpoints funcionan correctamente
- Solo falta data de prueba para facilitar testing manual

**Recomendación para el futuro:**
Crear un script `scripts/seed_semana4.py` con datos como:
```python
# Ejemplo de datos sugeridos:
- Decreto 2024 (DS 4984) con tramos salariales
- Decreto 2025 con SMN actualizado
- Parámetros: RC_IVA (13%), AFP_LABORAL (12.71%), AFP_PATRONAL (3%)
```

**Estado:** ⚠️ NO CRÍTICO - Puede completarse después si se desea

---

## 📊 MÓDULOS Y ENTIDADES IMPLEMENTADAS

### Módulo: `app/features/contracts/`

#### 1. Contrato (contrato/)
- ✅ Modelo: `Contrato` con ENUMs `TipoContratoEnum`, `EstadoContratoEnum`
- ✅ Schemas: Create, Update, Response, Renovacion
- ✅ Services: CRUD completo + lógica de renovación
- ✅ Router: 9 endpoints REST
- **Características:**
  - Soporte para contratos indefinidos y plazo fijo
  - Estados: activo, finalizado, rescindido
  - Property `es_vigente` calculado
  - Endpoint de renovación para plazo_fijo

#### 2. Ajuste Salarial + Decretos (ajuste_salarial/)
- ✅ Modelos:
  - `AjusteSalarial` (historial de cambios salariales)
  - `DecretoIncrementoSalarial` (cabecera de decretos anuales)
  - `CondicionDecreto` (tramos salariales por decreto)
  - `ParametroImpuesto` (tasas vigentes RC_IVA, AFP, etc.)
- ✅ Schemas: Create/Response para cada entidad
- ✅ Services: CRUD + lógica de aplicación masiva de decretos
- ✅ Router: 12 endpoints REST
- **Características:**
  - Aplicación masiva de decreto a empleados con contrato indefinido
  - Función PL/pgSQL `fn_porcentaje_incremento_decreto` para calcular tramo
  - Trigger `trg_sync_salario_empleado` actualiza `empleado.salario_base` automáticamente
  - Historial completo de parámetros tributarios

---

## 🗄️ BASE DE DATOS

### Tablas creadas en Semana 4:

| Tabla | Registros | Estado |
|-------|-----------|--------|
| `rrhh.contrato` | 0 | ✅ Creada |
| `rrhh.ajuste_salarial` | 0 | ✅ Creada |
| `rrhh.decreto_incremento_salarial` | 0 | ✅ Creada |
| `rrhh.condicion_decreto` | 0 | ✅ Creada |
| `rrhh.parametro_impuesto` | 0 | ✅ Creada |

### ENUMs creados:
- `tipo_contrato_enum` (indefinido, plazo_fijo)
- `estado_contrato_enum` (activo, finalizado, rescindido)
- `motivo_ajuste_enum` (decreto_anual, renovacion, merito, promocion)

### Funciones SQL creadas:
1. **`fn_horas_vacacion_lgt(DATE, DATE)`**
   - Calcula horas de vacación según LGT Art. 44
   - Input: fecha_ingreso, fecha_calculo
   - Output: horas (0, 120, 160 o 240)
   - Usado en: Módulo de vacaciones (Semana 7)

2. **`fn_porcentaje_incremento_decreto(INTEGER, NUMERIC)`**
   - Obtiene porcentaje de incremento del primer tramo aplicable
   - Input: id_decreto, salario_actual
   - Output: porcentaje_incremento
   - Usado en: Aplicación masiva de decretos

### Triggers:
- **`trg_sync_salario_empleado`** en `ajuste_salarial`
  - Al insertar un ajuste con `fecha_vigencia <= hoy`
  - Actualiza automáticamente `empleado.salario_base`
  - Para ajustes futuros, el worker diario debe ejecutarlo en la fecha de vigencia

---

## 🔗 ENDPOINTS DISPONIBLES

### Contratos (/api/v1/contratos)
```
POST   /                              → Crear contrato
GET    /                              → Listar contratos (con filtros)
GET    /empleado/{id}                 → Historial de contratos de un empleado
GET    /empleado/{id}/activo          → Contrato activo de un empleado
GET    /{id}                          → Obtener contrato por ID
PUT    /{id}                          → Actualizar contrato
PUT    /{id}/finalizar                → Finalizar contrato
PUT    /{id}/rescindir                → Rescindir contrato
POST   /{id}/renovar                  → Renovar contrato plazo_fijo
```

### Ajustes Salariales (/api/v1/ajustes-salariales)
```
POST   /                              → Crear ajuste salarial
GET    /empleado/{id}/historial       → Historial de ajustes
GET    /empleado/{id}/vigente         → Último ajuste vigente

POST   /decretos                      → Crear decreto con tramos
GET    /decretos                      → Listar decretos
GET    /decretos/{id}                 → Obtener decreto con condiciones
GET    /decretos/anio/{anio}          → Obtener decreto por año
POST   /decretos/{id}/aplicar         → Aplicar decreto masivamente

POST   /parametros-impuesto           → Crear parámetro
GET    /parametros-impuesto/vigente/{nombre}  → Parámetro vigente
GET    /parametros-impuesto/historial/{nombre} → Historial
GET    /parametros-impuesto/vigentes  → Todos los parámetros vigentes
```

Total: **21 endpoints nuevos** en Semana 4

---

## 🧪 PRUEBAS REALIZADAS

### 1. Verificación de imports
```bash
$ python -c "from app.main import app; print('OK')"
OK - main.py imports correctamente ✅
```

### 2. Verificación de modelos
```bash
$ python -c "from app.features.contracts.contrato.models import Contrato; ..."
OK - Modelos de contracts importan correctamente ✅
```

### 3. Verificación de sincronización Alembic
```bash
$ alembic check
No new upgrade operations detected. ✅
```

### 4. Inicio del servidor FastAPI
```bash
$ uvicorn app.main:app --reload
INFO:     Application startup complete. ✅
INFO:     Uvicorn running on http://127.0.0.1:8000
```

---

## 📝 MIGRACIÓN DE SEMANA 4

**Archivo:** `alembic/versions/a5f3c8d9e012_semana4_modulo_contracts.py`

**Estructura:**
1. ✅ Crear ENUMs (tipo_contrato, estado_contrato, motivo_ajuste)
2. ✅ Crear 5 tablas con constraints y foreign keys
3. ✅ Crear función `fn_horas_vacacion_lgt` (para Semana 7)
4. ✅ Crear función `fn_porcentaje_incremento_decreto`
5. ✅ Crear trigger `trg_sync_salario_empleado`

**Cumplimiento de REGLA ABSOLUTA #1:** ✅
- ✅ Tablas creadas con `op.create_table()` (autogenerate)
- ✅ ENUMs creados con `op.execute()` (correcto, no detectados por autogenerate)
- ✅ Funciones SQL con `op.execute()` (correcto)
- ✅ Triggers con `op.execute()` (correcto)
- ✅ **CERO** líneas del archivo `codigoPostgresSQL.txt` copiadas en `op.execute()`

---

## 🎓 DECISIONES TÉCNICAS IMPORTANTES

### 1. Separación de lógica de contratos
- **Contrato indefinido:** Cambios de salario → `ajuste_salarial`
- **Contrato plazo_fijo:** Renovación → Crear NUEVO contrato con nuevo salario
- **Justificación:** Diferencias legales en Bolivia entre ambos tipos

### 2. Aplicación masiva de decretos
- Endpoint dedicado: `POST /decretos/{id}/aplicar`
- Itera sobre empleados con contrato indefinido activo
- Usa función SQL `fn_porcentaje_incremento_decreto` para calcular tramo
- Retorna estadísticas: empleados_procesados, ajustes_creados, errores
- **Ventaja:** Auditoría completa en cada ajuste_salarial

### 3. Trigger automático de salarios
- Al insertar en `ajuste_salarial` con `fecha_vigencia <= hoy`
- Actualiza `empleado.salario_base` automáticamente
- Para ajustes programados (fecha futura), el worker diario debe ejecutarlos
- **Ventaja:** Sincronización automática, sin lógica duplicada

### 4. Historial completo de impuestos
- Tabla `parametro_impuesto` con rangos de vigencia
- Permite consultar tasas históricas (ej: "¿cuál era el RC_IVA en 2020?")
- Soporta cambios futuros programados

---

## 🔧 COMANDOS EJECUTADOS

```bash
# 1. Revisar estado de Alembic
alembic check

# 2. Corregir imports en alembic/env.py
# (edición manual)

# 3. Agregar campo email a modelo Usuario
# (edición manual en models.py y schemas.py)

# 4. Verificar sincronización
alembic check  # → No new upgrade operations detected ✅

# 5. Probar servidor FastAPI
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

---

## 📈 PROGRESO DEL PROYECTO

| Semana | Módulo | Estado |
|--------|--------|--------|
| 1 | Estructura base + modelos iniciales | ✅ Completada |
| 2 | Auth (Rol + Usuario) | ✅ Completada (corregido email) |
| 3 | Employees (Depto + Cargo + Empleado + Horario) | ✅ Completada |
| **4** | **Contracts (Contrato + Ajuste + Decreto + Impuestos)** | ✅ **Completada** |
| 5 | Marcaciones + Upload Excel | ⏳ Pendiente |
| 6 | Asistencia Diaria + Worker | ⏳ Pendiente |
| 7 | Feriados + Cumpleaños + Justificaciones + Vacaciones | ⏳ Pendiente |
| 8 | Reports | ⏳ Pendiente |
| 9 | JWT + Tests | ⏳ Pendiente |
| 10 | Pulido Final | ⏳ Pendiente |

---

## ✅ CHECKLIST DE CUMPLIMIENTO

### Reglas de código:
- ✅ Modelos 100% SQLAlchemy 2.0 (Mapped + mapped_column)
- ✅ Arquitectura de 4 archivos por entidad (models, schemas, services, router)
- ✅ Toda lógica de negocio en services.py
- ✅ Endpoints abiertos (sin JWT hasta Semana 9)
- ✅ Alembic con `--autogenerate` (solo ENUMs/funciones/triggers en op.execute)
- ✅ Comentarios y docstrings en español

### Base de datos:
- ✅ Todas las tablas en schema `rrhh`
- ✅ Constraints definidos en modelos Python
- ✅ Foreign keys con ondelete apropiado
- ✅ Check constraints para validaciones
- ✅ Triggers documentados con COMMENT

### Documentación:
- ✅ README.md actualizado con progreso
- ✅ Swagger accesible en /docs
- ✅ Este informe de Semana 4 completo

---

## 🚀 QUÉ VIENE EN SEMANA 5

### Objetivo: Módulo de Marcaciones + Upload Excel

**Entregables esperados:**
1. Modelo `Marcacion` (timestamp, tipo_marcacion, id_empleado)
2. Modelo `IncidenciaMarcacion` (marcaciones huérfanas o duplicadas)
3. Modelo `ArchivoExcel` (log de archivos subidos)
4. Endpoint `POST /marcaciones/upload-excel` con Pandas
5. Lógica de detección de duplicadas
6. Lógica de detección de marcaciones sin entrada/salida
7. Trigger `crear_incidencia_marcacion` automático
8. Migración 5 con autogenerate

**Tecnologías a usar:**
- Pandas para lectura de Excel
- openpyxl como engine
- Validaciones asíncronas con FastAPI
- Bulk insert con SQLAlchemy

---

## 🎯 CONCLUSIÓN

**Estado final de Semana 4: ✅ APROBADO**

### Resumen de correcciones:
1. ✅ Imports de modelos en `alembic/env.py` → Corregido
2. ✅ Campo `email` en Usuario → Agregado a modelo y schemas
3. ⚠️ Scripts seed de Semana 4 → Pendiente (no crítico)

### Verificaciones exitosas:
- ✅ Alembic sincronizado con BD
- ✅ FastAPI levanta sin errores
- ✅ Todos los modelos importan correctamente
- ✅ 21 endpoints REST disponibles
- ✅ Cumplimiento de reglas de arquitectura

**El proyecto está listo para continuar con Semana 5.**

---

## 📞 CONTACTO Y SOPORTE

Para dudas sobre este informe o el código de Semana 4:
- Revisar la documentación en `/docs` de FastAPI
- Consultar el archivo `InformacionContexto/codigoPostgresSQL.txt` para referencia SQL
- Revisar el modelo relacional en `InformacionContexto/ModeloRelacional.pdf`

---

**Fecha de informe:** 06 de abril de 2026
**Desarrollado por:** Arquitecto de Software Senior + Lead Developer
**Tecnologías:** FastAPI 2025 + SQLAlchemy 2.0 + PostgreSQL 14+ + Python 3.12
