# 📋 Orden de Creación de Entidades - Arquitectura de Dependencias

## Introducción

Este documento define el **árbol jerárquico de dependencias** para la creación de entidades en el Sistema RRHH Bolivia. 

**REGLA FUNDAMENTAL**: No se puede crear ni poblar una entidad de un nivel superior sin antes haber resuelto TODAS sus dependencias del nivel inferior.

---

## 📊 Árbol Completo de Dependencias

```
NIVEL 0 (Sin dependencias - Tablas Base Fundacionales)
├─ ci_depto_emision_ref (ComplementoDep)
│  └─ Códigos SEGIP de Bolivia (LP, CB, SC, OR, PT, TJ, CH, BE, PD)
│  └─ SCRIPT: seed_base_data.py → seed_ci_depto_emision_ref()
│
├─ rol
│  └─ Roles del sistema (admin, rrhh, supervisor, empleado, consulta)
│  └─ SCRIPT: seed_base_data.py → seed_roles()
│
├─ departamento (estructura jerárquica)
│  └─ Raíz: Gerencia General (id_padre=NULL)
│  └─ Nivel 1: Gerencia RRHH, Administrativa, Comercial, Sistemas
│  └─ Nivel 2+: Áreas subordinadas (jerárquico)
│  └─ SCRIPT: seed_base_data.py → seed_departamentos()
│
└─ decreto_incremento_salarial (cabecera de decretos anuales)
   └─ DS 4984 / 2024 (SMN 2500 Bs, vigente 01/may/2024)
   └─ Incluye: CondicionDecreto (tramos salariales)
   └─ SCRIPT: seed_base_data.py → seed_decreto_incremento_salarial()


NIVEL 1 (Dependen de Nivel 0)
├─ cargo
│  ├─ FK: departamento ← NIVEL 0
│  └─ Ejemplo: Gerente General, Analista Nóminas, etc.
│  └─ SCRIPT: seed_nivel_1.py → seed_cargos()
│
├─ condicion_decreto
│  ├─ FK: decreto_incremento_salarial ← NIVEL 0
│  └─ Tramos salariales (orden, salario_desde, salario_hasta, %)
│  └─ Nota: Ya se crea en seed_base_data.py
│
└─ parametro_impuesto (independiente)
   └─ RFC_IVA, AFP_LABORAL, AFP_PATRONAL, etc.
   └─ SCRIPT: seed_nivel_1.py → seed_parametros_impuesto()


NIVEL 2 (Dependen de Nivel 1)
└─ empleado
   ├─ FK: ci_depto_emision_ref ← NIVEL 0
   ├─ FK: cargo ← NIVEL 1
   ├─ FK: departamento ← NIVEL 0
   └─ Datos: CI, nombre, email, salario_base, etc.
   └─ SCRIPT: seed_nivel_2.py → seed_empleados()


NIVEL 3 (Dependen de Nivel 2)
├─ usuario
│  ├─ FK: empleado ← NIVEL 2
│  ├─ FK: rol ← NIVEL 0
│  └─ Datos: username, contraseña, activo, etc.
│  └─ SCRIPT: seed_nivel_3.py → seed_usuarios()
│
├─ contrato
│  ├─ FK: empleado ← NIVEL 2
│  ├─ FK: decreto_incremento_salarial ← NIVEL 0 (opcional)
│  └─ Datos: tipo_contrato, fecha_inicio, salario_base, etc.
│  └─ SCRIPT: seed_nivel_3.py → seed_contratos()
│
├─ horario (independiente de empleado, pero relacionado)
│  └─ Datos: nombre, hora_entrada, hora_salida, dias_laborales
│  └─ SCRIPT: seed_nivel_3.py → seed_horarios()
│
└─ asignacion_horario
   ├─ FK: empleado ← NIVEL 2
   ├─ FK: horario ← NIVEL 3
   └─ Datos: fecha_inicio, fecha_fin
   └─ SCRIPT: seed_nivel_3.py → seed_asignaciones_horario()


NIVEL 4+ (Operaciones Diarias - Dependen de empleado)
├─ marcacion
│  ├─ FK: empleado ← NIVEL 2
│  ├─ FK: asignacion_horario ← NIVEL 3
│  └─ Datos: fecha, hora_entrada, hora_salida, estado, etc.
│
├─ asistencia_diaria
│  ├─ FK: empleado ← NIVEL 2
│  └─ Datos: fecha, presente, justificacion_id, etc.
│
├─ vacacion
│  ├─ FK: empleado ← NIVEL 2
│  └─ Datos: fecha_inicio, fecha_fin, dias_solicitados, estado
│
├─ justificacion
│  ├─ FK: empleado ← NIVEL 2
│  └─ Datos: fecha, motivo, documento, estado
│
├─ dia_festivo
│  ├─ FK: complemento_dep (ci_depto_emision_ref) ← NIVEL 0
│  └─ Datos: fecha, nombre (Día de la Patria, etc.)
│
└─ reporte
   └─ Datos derivados de: marcacion, asistencia_diaria, vacacion, etc.
   └─ Lectura: No inserta datos, solo consulta
```

---

## 🔄 Secuencia de Ejecución Recomendada

### **PASO 1: NIVEL 0 (Fundacional)**
```bash
# Ejecutar UNA sola vez
python scripts/seed_base_data.py
```

**Crea:**
- 9 códigos departamentales SEGIP (LP, CB, SC, etc.)
- 5 roles del sistema (admin, rrhh, supervisor, empleado, consulta)
- Estructura jerárquica de departamentos (Gerencia General + 4 gerencias)
- Decreto 2024 con 3 tramos salariales

**Validar:** Consultar DB:
```sql
SELECT * FROM rrhh.complemento_dep;
SELECT * FROM rrhh.rol;
SELECT * FROM rrhh.departamento;
SELECT * FROM rrhh.decreto_incremento_salarial;
```

---

### **PASO 2: NIVEL 1 (Nivel Intermedio)**
```bash
# Ejecutar DESPUÉS de NIVEL 0
python scripts/seed_nivel_1.py
```

**Crea:**
- Cargos organizacionales (vinculados a departamentos)
- Parámetros de impuesto (AFP, IVA, etc.)

**Dependencias:**
- `cargo` → requiere `departamento` (NIVEL 0) ✓
- `parametro_impuesto` → independiente ✓

---

### **PASO 3: NIVEL 2 (Empleados)**
```bash
# Ejecutar DESPUÉS de NIVEL 1
python scripts/seed_nivel_2.py
```

**Crea:**
- Empleados de ejemplo (10-20 empleados reales)

**Dependencias:**
- `empleado` → requiere `ci_depto_emision_ref` (NIVEL 0) ✓
- `empleado` → requiere `cargo` (NIVEL 1) ✓
- `empleado` → requiere `departamento` (NIVEL 0) ✓

---

### **PASO 4: NIVEL 3 (Usuarios, Contratos, Horarios)**
```bash
# Ejecutar DESPUÉS de NIVEL 2
python scripts/seed_nivel_3.py
```

**Crea:**
- Usuario admin + usuarios operacionales
- Contratos para empleados
- Horarios base (Jornada Normal, Turno Nocturno, etc.)
- Asignaciones de horario

**Dependencias:**
- `usuario` → requiere `empleado` (NIVEL 2) ✓
- `usuario` → requiere `rol` (NIVEL 0) ✓
- `contrato` → requiere `empleado` (NIVEL 2) ✓
- `horario` → independiente ✓
- `asignacion_horario` → requiere `empleado` (NIVEL 2) ✓

---

### **PASO 5: NIVEL 4+ (Opcional - Datos de Operación)**
```bash
# Ejecutar después de NIVEL 3 si es necesario
# Generalmente se generan por el uso del sistema
python scripts/seed_nivel_4_opcional.py
```

**Crea (opcional):**
- Marcaciones de ejemplo
- Asistencias de ejemplo
- Vacaciones de ejemplo
- Justificaciones de ejemplo

---

## ⚠️ Reglas de Integridad de Referencia

### **Campos Mandatorios (NO NULL)**
```
ComplementoDep:
  - codigo (PK)
  - nombre_departamento

Rol:
  - nombre (UNIQUE)
  - activo

Departamento:
  - nombre
  - codigo (UNIQUE)
  - activo
  (id_padre puede ser NULL solo para raíz)

DecretoIncrementoSalarial:
  - anio (UNIQUE)
  - nuevo_smn (Decimal > 0)
  - fecha_vigencia
  - referencia_decreto

CondicionDecreto:
  - id_decreto (FK)
  - orden
  - porcentaje_incremento
  (salario_desde y salario_hasta pueden ser NULL)
```

### **Constraints Especiales**

1. **Departamento (autorreferencia)**
   - `id_padre` apunta a otro departamento o es NULL
   - Validación: Evitar ciclos

2. **CondicionDecreto**
   - `salario_desde < salario_hasta` (si ambos no son NULL)
   - `porcentaje_incremento >= 0`

3. **Decreto (uniqueness)**
   - Un decreto por año
   - Validar que `fecha_vigencia` sea coherente

---

## 🔍 Checklist para Nuevas Entidades

Antes de modelar una nueva entidad, responde:

1. **¿Cuáles son sus dependencias?**
   - ¿Qué otras entidades debe referenciar?
   - ¿De qué nivel están esas dependencias?

2. **¿En qué nivel debe estar?**
   - NIVEL 0: Sin dependencias
   - NIVEL 1: Depende solo de NIVEL 0
   - NIVEL 2: Depende de NIVEL 0 y/o NIVEL 1
   - NIVEL 3+: Depende de entidades anteriores

3. **¿Qué campos son mandatorios?**
   - Todos los campos sin `nullable=True` deben tener data
   - No insertar NULL en campos clave para reportes legales

4. **¿Cómo se inserta data?**
   - Crear `seed_nivelN.py` correspondiente
   - Incluir documentación de restricciones
   - Usar transacciones con rollback en errores

5. **¿Se necesitan índices?**
   - Campos de búsqueda frecuente: INDEX
   - FKs: Automático
   - Campos únicos: UNIQUE

---

## 📝 Ejemplo: Agregar Entidad Nueva

**Supongamos que queremos agregar `puesto_vacante`:**

1. **Análisis de dependencias:**
   - Necesita: `cargo` (NIVEL 1), `departamento` (NIVEL 0)
   - Conclusión: Es NIVEL 2 (porque depende de NIVEL 1)

2. **Crear modelo en `models.py`:**
   ```python
   class PuestoVacante(Base):
       id: Mapped[int] = mapped_column(primary_key=True)
       id_cargo: Mapped[int] = mapped_column(ForeignKey("cargo.id"), nullable=False)
       id_departamento: Mapped[int] = mapped_column(ForeignKey("departamento.id"), nullable=False)
       cantidad_vacantes: Mapped[int] = mapped_column(nullable=False)
       activo: Mapped[bool] = mapped_column(default=True)
   ```

3. **Crear migración:**
   ```bash
   alembic revision --autogenerate -m "Agregar puesto_vacante"
   alembic upgrade head
   ```

4. **Crear seed en `seed_nivel_2.py`:**
   ```python
   def seed_puestos_vacantes(db):
       # Obtener cargos y departamentos (NIVEL 1 y 0)
       gerente = db.query(Cargo).filter_by(nombre="Gerente General").first()
       rrhh = db.query(Departamento).filter_by(codigo="RRHH").first()
       
       puesto = PuestoVacante(
           id_cargo=gerente.id,
           id_departamento=rrhh.id,
           cantidad_vacantes=2,
           activo=True
       )
       db.add(puesto)
       db.commit()
   ```

5. **Actualizar este documento:**
   - Agregar a NIVEL 2 en el árbol
   - Documentar dependencias
   - Incluir en checklist

---

## 🚨 Errores Comunes

| Error | Causa | Solución |
|-------|-------|----------|
| `IntegrityError: foreign key violation` | FK apunta a entidad no poblada | Ejecutar seeds en orden NIVEL 0 → NIVEL 1 → ... |
| `NOT NULL constraint failed` | Campo mandatorio sin valor | Revisar reglas de integridad de la entidad |
| `UNIQUE constraint failed` | Duplicado en campo UNIQUE | Verificar `seed_xxx()` con `.first()` antes de insertar |
| `Ciclo en autorreferencia (departamento)` | id_padre apunta a sí mismo o ciclo | Validar jerarquía antes de insertar |

---

## 📞 Preguntas Frecuentes

**P: ¿Qué pasa si ejecuto seeds fuera de orden?**
A: Fallará con `IntegrityError: foreign key violation`. Debes ejecutar en orden NIVEL 0 → NIVEL 1 → ...

**P: ¿Puedo ejecutar un seed dos veces?**
A: Sí, los scripts validan con `.first()` antes de insertar. Si ya existe, omite.

**P: ¿Cómo elimino datos y vuelvo a comenzar?**
A:
```bash
# Resetear base de datos
alembic downgrade base  # Elimina todas las tablas
alembic upgrade head    # Recrea tablas
python scripts/seed_base_data.py  # Nivel 0 nuevamente
```

**P: ¿Puedo tener departamentos sin subordinados?**
A: Sí, es válido. Solo necesita `nombre`, `codigo`, `id_padre` (NULL si es raíz).

**P: ¿Por qué complicar con niveles?**
A: Para garantizar integridad de datos. Una FK rota es un desastre en reportes legales.

---

## 🔗 Relaciones Cruzadas Importantes

```
empleado
├─ pertenece a departamento (NIVEL 0)
├─ ocupa cargo (NIVEL 1)
└─ se emite CI en complemento_dep (NIVEL 0)

usuario
├─ representa a empleado (NIVEL 2)
└─ tiene rol (NIVEL 0)

contrato
├─ vincula empleado (NIVEL 2)
├─ referencia decreto (NIVEL 0, opcional)
└─ genera ajuste_salarial (NIVEL 4)

marcacion
├─ registra a empleado (NIVEL 2)
└─ vincula asignacion_horario (NIVEL 3)
```

---

## ✅ Validación Final

Después de ejecutar todos los seeds, ejecuta:

```sql
-- Verificar datos NIVEL 0
SELECT COUNT(*) as complementos FROM rrhh.complemento_dep;  -- Debe ser 9
SELECT COUNT(*) as roles FROM rrhh.rol;                      -- Debe ser 5
SELECT COUNT(*) as departamentos FROM rrhh.departamento;     -- Debe ser 7+
SELECT COUNT(*) as decretos FROM rrhh.decreto_incremento_salarial;  -- Debe ser 1+

-- Verificar integridad
SELECT * FROM rrhh.departamento WHERE id_padre IS NULL;  -- Solo 1 raíz
SELECT * FROM rrhh.decreto_incremento_salarial;          -- Sanidad de datos
SELECT * FROM rrhh.condicion_decreto ORDER BY orden;     -- Tramos en orden
```

---

**Última actualización:** 2026-04-14  
**Versión:** 1.0 - Arquitectura NIVEL 0-3  
**Mantenedor:** Sistema RRHH Bolivia MVP
