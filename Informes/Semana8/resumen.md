# Sistema RRHH Bolivia - Semana 8: Modulo Reports

**Fecha:** 10 de Abril de 2026  
**Stack:** FastAPI + Uvicorn + SQLAlchemy 2.0 puro + Alembic + PostgreSQL

## Que se construyo

1. **Entidad Reporte (bitacora de generaciones)**
   - Se creo la carpeta `app/features/reports/reporte/` con 4 archivos de entidad:
     - `models.py`
     - `schemas.py`
     - `services.py`
     - `router.py`
   - Modelo `Reporte` con:
     - tipo de reporte (`asistencia_mensual`, `planilla`, `vacaciones`, `individual`)
     - formato (`XLSX`, `PDF`, `CSV`)
     - filtros de contexto (`id_departamento`, `id_empleado`, `id_generado_por`)
     - periodo de reporte y ruta de archivo
     - `activo` para soft delete

2. **Generacion de reportes exportables**
   - XLSX de asistencia mensual.
   - XLSX de planilla.
   - XLSX de vacaciones.
   - PDF individual por empleado.
   - Todos los reportes se guardan en `REPORTS_DIR` y se registran en `rrhh.reporte`.

3. **Endpoints abiertos (sin JWT) del modulo reportes**
   - `POST /api/v1/reportes/asistencia-mensual`
   - `POST /api/v1/reportes/planilla`
   - `POST /api/v1/reportes/vacaciones`
   - `POST /api/v1/reportes/individual/{id_empleado}`
   - `GET /api/v1/reportes/`
   - `GET /api/v1/reportes/{reporte_id}`
   - `GET /api/v1/reportes/{reporte_id}/descargar`
   - `PUT /api/v1/reportes/{reporte_id}`
   - `DELETE /api/v1/reportes/{reporte_id}` (soft delete)
   - `DELETE /api/v1/reportes/{reporte_id}/permanente` (hard delete)

4. **Migracion Semana 8 con autogenerate**
   - Revision generada con:
     - `alembic revision --autogenerate -m "semana8_modulo_reports"`
   - Archivo creado:
     - `alembic/versions/cfc064401f07_semana8_modulo_reports.py`
   - Incluye:
     - `create_table` de `rrhh.reporte` (autogenerate)
     - `op.execute()` para crear vista `rrhh.v_saldo_impuestos_planilla`

5. **Integracion general del sistema**
   - Se habilito import de `Reporte` en `alembic/env.py`.
   - Se activo el router de reportes en `app/main.py`.
   - Se incluyo `reportlab==4.2.5` en `requirements.txt` para PDF.
   - Se restauro el FK de `asistencia_diaria.id_justificacion` en el modelo para evitar drift de esquema.

## Comandos ejecutados en terminal

```bash
python -m compileall app
python -c "from app.main import app; print('OK')"

venv\Scripts\python.exe -m alembic revision --autogenerate -m "semana8_modulo_reports"
venv\Scripts\python.exe -m alembic upgrade head
venv\Scripts\python.exe -m alembic current
venv\Scripts\python.exe -m alembic history --verbose

venv\Scripts\python.exe -m compileall app
venv\Scripts\python.exe -c "from app.main import app; print('OK')"
venv\Scripts\python.exe -m pytest

venv\Scripts\python.exe -m pip install reportlab==4.2.5
```

## Decisiones tecnicas importantes

1. **Alembic autogenerate como fuente principal para tablas/columnas**
   - La tabla `rrhh.reporte` se genero por autogenerate.
   - Solo se uso `op.execute()` para la vista `v_saldo_impuestos_planilla` (permitido por regla).

2. **Bitacora transaccional por cada archivo generado**
   - Cada exportacion crea un registro en `rrhh.reporte`.
   - Se conserva trazabilidad de quien genero, para quien y en que periodo.

3. **Soft delete + hard delete en entidad operativa Reporte**
   - Soft delete via campo `activo`.
   - Hard delete disponible en endpoint separado.

4. **Vista SQL para planilla mensual**
   - `rrhh.v_saldo_impuestos_planilla` calcula base de descuento por retrasos/ausencias y aplica tasas vigentes (AFP/RC-IVA) por vigencia de `parametro_impuesto`.
   - Esta vista desacopla calculo legal de la capa HTTP y simplifica el XLSX de planilla.

5. **Endpoints abiertos hasta Semana 9**
   - No se implemento JWT ni dependencias de autenticacion, cumpliendo la regla del plan semanal.

## Que viene la proxima semana (Semana 9)

1. Activar autenticacion JWT en todos los endpoints.
2. Implementar `get_current_user` y control de roles (Admin, RRHH, Supervisor, Empleado).
3. Agregar tests con pytest para modulos criticos (auth, employees, asistencia, reports).
4. Endurecer validaciones de seguridad y errores HTTP consistentes.

## Nota de contexto

- Los archivos PDF de `InformacionContexto/` no pudieron ser leidos por la herramienta del modelo actual.
- Se uso como fuente de verdad el contenido legible de `MermaidLive-Code.txt` y `codigoPostgresSQL.txt` (sin copiar SQL directo en migraciones fuera de lo permitido).
