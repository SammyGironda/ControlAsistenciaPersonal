# 🧪 GUÍA DE TESTING MANUAL - SEMANA 4

## 📋 Pre-requisitos
1. Aplicar migración: `alembic upgrade head`
2. Iniciar servidor: `uvicorn app.main:app --reload --port 8000`
3. Abrir Swagger: http://localhost:8000/docs

## ✅ TEST 1: Crear Contrato Indefinido

### Paso 1: Crear contrato para empleado existente
```http
POST /api/v1/contratos
Content-Type: application/json

{
  "id_empleado": 1,
  "tipo_contrato": "indefinido",
  "fecha_inicio": "2024-01-01",
  "fecha_fin": null,
  "salario_base": 3500.00,
  "observacion": "Contrato inicial"
}
```

**Verificar:**
- ✅ Respuesta 201 Created
- ✅ Campo `estado` = "activo"
- ✅ Campo `es_vigente` = true

## ✅ TEST 2: Crear Contrato Plazo Fijo

```http
POST /api/v1/contratos
Content-Type: application/json

{
  "id_empleado": 2,
  "tipo_contrato": "plazo_fijo",
  "fecha_inicio": "2024-01-01",
  "fecha_fin": "2024-12-31",
  "salario_base": 3000.00,
  "observacion": "Contrato temporal"
}
```

**Verificar:**
- ✅ Respuesta 201 Created
- ✅ `fecha_fin` está presente

## ✅ TEST 3: Crear Decreto con Tramos

```http
POST /api/v1/ajustes-salariales/decretos
Content-Type: application/json

{
  "anio": 2024,
  "nuevo_smn": 2500.00,
  "fecha_vigencia": "2024-05-01",
  "referencia_decreto": "DS 4984",
  "condiciones": [
    {
      "orden": 1,
      "salario_desde": null,
      "salario_hasta": 2500.00,
      "porcentaje_incremento": 5.00
    },
    {
      "orden": 2,
      "salario_desde": 2501.00,
      "salario_hasta": 5000.00,
      "porcentaje_incremento": 3.00
    },
    {
      "orden": 3,
      "salario_desde": 5001.00,
      "salario_hasta": null,
      "porcentaje_incremento": 1.00
    }
  ]
}
```

**Verificar:**
- ✅ Respuesta 201 Created
- ✅ `condiciones` array tiene 3 elementos
- ✅ Cada condición tiene su `orden` correcto

## ✅ TEST 4: Aplicar Decreto a Empleados

```http
POST /api/v1/ajustes-salariales/decretos/{decreto_id}/aplicar
Content-Type: application/json

{
  "id_aprobado_por": 1
}
```

**Verificar:**
- ✅ Respuesta 200 OK
- ✅ `empleados_procesados` > 0
- ✅ `ajustes_creados` > 0
- ✅ `errores` está vacío o con errores esperados

### Verificar en BD (opcional con DBeaver/pgAdmin):
```sql
-- Ver ajustes creados
SELECT * FROM rrhh.ajuste_salarial 
WHERE motivo = 'decreto_anual' 
ORDER BY created_at DESC;

-- Verificar que salario_base se actualizó
SELECT id, nombres, apellidos, salario_base 
FROM rrhh.empleado 
WHERE estado = 'activo';
```

## ✅ TEST 5: Renovar Contrato Plazo Fijo

```http
POST /api/v1/contratos/{contrato_id}/renovar
Content-Type: application/json

{
  "fecha_inicio": "2025-01-01",
  "fecha_fin": "2025-12-31",
  "salario_base": 3300.00,
  "observacion": "Renovación con incremento 10%"
}
```

**Verificar:**
- ✅ Respuesta 201 Created (nuevo contrato)
- ✅ Contrato anterior tiene estado = "finalizado"
- ✅ Nuevo contrato tiene estado = "activo"

## ✅ TEST 6: Crear Ajuste Salarial Manual

```http
POST /api/v1/ajustes-salariales/
Content-Type: application/json

{
  "id_empleado": 1,
  "id_contrato": 1,
  "salario_anterior": 3500.00,
  "salario_nuevo": 4000.00,
  "fecha_vigencia": "2024-06-01",
  "motivo": "merito",
  "id_aprobado_por": 5,
  "observacion": "Incremento por desempeño destacado"
}
```

**Verificar:**
- ✅ Respuesta 201 Created
- ✅ Consultar GET `/api/v1/empleados/1` y verificar que `salario_base` = 4000.00

## ✅ TEST 7: Crear Parámetros de Impuestos

```http
POST /api/v1/ajustes-salariales/parametros-impuesto
Content-Type: application/json

{
  "nombre": "RC_IVA",
  "porcentaje": 13.00,
  "fecha_vigencia_inicio": "1992-01-01",
  "fecha_vigencia_fin": null,
  "descripcion": "Régimen Complementario al IVA"
}
```

```http
POST /api/v1/ajustes-salariales/parametros-impuesto
Content-Type: application/json


{
  "nombre": "AFP_LABORAL",
  "porcentaje": 12.71,
  "fecha_vigencia_inicio": "2020-01-01",
  "fecha_vigencia_fin": null,
  "descripcion": "Aporte trabajador (10% jubilación + 1.71% riesgo + 1% solidario)"
}
```

**Verificar:**
- ✅ Respuesta 201 Created para ambos
- ✅ GET `/api/v1/ajustes-salariales/parametros-impuesto/vigentes` retorna ambos

## 🔴 TESTS DE VALIDACIÓN (deben fallar)

### Test 1: Crear contrato con empleado que ya tiene uno activo
```http
POST /api/v1/contratos
{
  "id_empleado": 1,
  "tipo_contrato": "indefinido",
  "fecha_inicio": "2024-06-01",
  "fecha_fin": null,
  "salario_base": 4000.00
}
```
**Esperado:** 400 Bad Request - "El empleado ya tiene un contrato activo"

### Test 2: Crear contrato plazo_fijo sin fecha_fin
```http
POST /api/v1/contratos
{
  "id_empleado": 3,
  "tipo_contrato": "plazo_fijo",
  "fecha_inicio": "2024-01-01",
  "fecha_fin": null,
  "salario_base": 3000.00
}
```
**Esperado:** 422 Validation Error - "Contrato plazo_fijo debe tener fecha_fin"

### Test 3: Crear ajuste con salarios iguales
```http
POST /api/v1/ajustes-salariales/
{
  "id_empleado": 1,
  "id_contrato": 1,
  "salario_anterior": 3500.00,
  "salario_nuevo": 3500.00,
  "fecha_vigencia": "2024-06-01",
  "motivo": "merito"
}
```
**Esperado:** 422 Validation Error - "salario_nuevo debe ser diferente a salario_anterior"

## ✅ CHECKLIST FINAL

- [ ] Todas las tablas fueron creadas correctamente
- [ ] Funciones PL/pgSQL están disponibles
- [ ] Trigger trg_sync_salario_empleado funciona
- [ ] Contratos indefinidos se crean correctamente
- [ ] Contratos plazo_fijo requieren fecha_fin
- [ ] Decretos se crean con sus tramos
- [ ] Aplicación masiva de decreto funciona
- [ ] Trigger actualiza empleado.salario_base automáticamente
- [ ] Renovación de contrato plazo_fijo crea nuevo contrato
- [ ] Parámetros de impuestos se consultan correctamente
- [ ] Swagger muestra todos los endpoints
- [ ] Validaciones Pydantic funcionan correctamente

## 📝 NOTA IMPORTANTE

**El trigger trg_sync_salario_empleado SOLO actualiza empleado.salario_base si fecha_vigencia <= CURRENT_DATE.**

Si creas un ajuste con fecha_vigencia futura, el salario NO se actualiza hasta que llegue esa fecha.
En Semana 6 crearemos un worker diario que procesará ajustes pendientes.
