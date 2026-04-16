================================================================================
SISTEMA RRHH BOLIVIA - DOCUMENTACION DE SEED (POBLADO DE DATOS)
================================================================================

ARCHIVOS CREADOS:
-----------------

1. seed_base_data.py
   - Script ejecutable que popula el NIVEL 0 (entidades base)
   - Inserta: ComplementoDep, Rol, Departamento, DecretoIncrementoSalarial
   - Uso: python scripts/seed_base_data.py
   - Idempotente: Se puede ejecutar multiples veces sin problemas

2. orden_creacion_entidades.md
   - Documento de arquitectura de dependencias
   - Define el arbol jerarquico 5 niveles de entidades
   - Guia para crear nuevas entidades respetando integridad referencial
   - LECTURA OBLIGATORIA antes de modelar nuevas tablas

3. GUIA_USO.md (en esta carpeta)
   - Guia completa de uso del sistema de seed
   - Instrucciones paso a paso
   - Troubleshooting y soluciones comunes
   - Consultas SQL de validacion

FLUJO DE EJECUCION RECOMENDADO:
------------------------------

Paso 1: Crear base de datos
  CREATE DATABASE rrhh_bolivia;

Paso 2: Ejecutar migraciones
  alembic upgrade head

Paso 3: Poblacion de datos (NIVEL 0)
  python scripts/seed_base_data.py

Paso 4: Verificar
  psql -U postgres -d rrhh_bolivia -c "SELECT COUNT(*) FROM rrhh.rol;"

NIVEL 0 QUE SE POPULA:
---------------------

✓ ComplementoDep (ci_depto_emision_ref): 9 codigos departamentales
  - LP: La Paz
  - CB: Cochabamba
  - SC: Santa Cruz
  - OR: Oruro
  - PT: Potosí
  - TJ: Tarija
  - CH: Chuquisaca
  - BE: Beni
  - PD: Pando

✓ Rol: 5 roles del sistema
  - admin: Acceso total
  - rrhh: Gestion de empleados
  - supervisor: Aprueba permisos
  - empleado: Consulta su informacion
  - consulta: Solo lectura

✓ Departamento: Estructura jerarquica (7 entidades)
  - Gerencia General (raiz)
  ├─ Gerencia RRHH (con 2 areas)
  ├─ Gerencia Administrativa
  ├─ Gerencia Comercial
  └─ Gerencia de Sistemas

✓ DecretoIncrementoSalarial: 1 decreto con 3 tramos
  - DS 4984 / 2024
  - SMN: 2500 Bs
  - Vigencia: 1 mayo 2024
  - Tramos: 5%, 3%, 1%

INTEGRACION CON MIGRACIONES:
----------------------------

El script usa SQL directo para evitar problemas de imports.
No se crea Base.metadata - Las migraciones de Alembic son OBLIGATORIAS.

Secuencia correcta:
  1. alembic upgrade head (crea todas las tablas vacias)
  2. python scripts/seed_base_data.py (puebla datos base)
  3. seed_nivel_1.py, seed_nivel_2.py, etc.

PROXIMO DESARROLLO:
------------------

Falta crear para NIVEL 1+:
  - seed_nivel_1.py: Cargo, ParametroImpuesto
  - seed_nivel_2.py: Empleado
  - seed_nivel_3.py: Usuario, Contrato, Horario, AsignacionHorario

Consulta orden_creacion_entidades.md para detalles.

ADVERTENCIAS IMPORTANTES:
------------------------

❌ NO ejecutes Base.metadata.create_all() - Las tablas ya existen por Alembic
❌ NO modifiques el seed_base_data.py directamente - Usa GUIA_USO.md
❌ NO saltes niveles - Los datos de NIVEL 1 necesitan NIVEL 0 poblado
✓ SI ejecuta multiples veces - El script valida antes de insertar

SOPORTE Y DOCUMENTACION:
-----------------------

- GUIA_USO.md: Instrucciones detalladas
- orden_creacion_entidades.md: Arquitectura y dependencias
- README.md (raiz): Documentacion general del proyecto
- app/db/base.py: Configuracion base de SQLAlchemy

Version: 1.0
Fecha: 2026-04-14
Sistema: RRHH Bolivia MVP
