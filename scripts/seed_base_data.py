"""
Script de Datos Semilla - NIVEL 0 (Entidades Base)
=====================================================

Popula las tablas fundacionales del sistema RRHH Bolivia.
ABSOLUTAMENTE CRÍTICO: Estos datos son mandatorios y NO pueden tener valores NULL.

NIVEL 0 (Sin dependencias):
├─ ci_depto_emision_ref (ComplementoDep - Códigos SEGIP de Bolivia)
├─ rol (Roles del sistema)
├─ departamento (Estructura organizacional jerárquica)
└─ decreto_incremento_salarial (Decretos base históricos)

RESTRICCIONES DE INTEGRIDAD:
- Todos los campos no marcados como nullable deben tener valor.
- Los valores deben ser reales y coherentes para contexto boliviano.
- Manejo de excepciones y rollback en caso de cualquier error.

Uso:
    python scripts/seed_base_data.py
"""

import sys
import io
from datetime import date
from decimal import Decimal
from pathlib import Path

# Forzar UTF-8 en Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Agregar el directorio raíz al path para importar los modelos
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import SessionLocal, engine
from app.db.base import Base

# ============================================================
# IMPORTANTE: Importar modelos directamente sin pasar por __init__
# para evitar imports de FastAPI que pueden no estar disponibles
# ============================================================
from sqlalchemy import text


def seed_ci_depto_emision_ref(db):
    """
    NIVEL 0: Insertar códigos de departamento de Bolivia para emisión de CI (SEGIP).
    Estos códigos son el estándar oficial del Servicio General de Identificación Personales.
    """
    print("\n[NIVEL 0] Insertando catalogo SEGIP (ci_depto_emision_ref)...")

    departamentos_segip = [
        {"codigo": "LP", "nombre_departamento": "La Paz", "activo": True},
        {"codigo": "CB", "nombre_departamento": "Cochabamba", "activo": True},
        {"codigo": "SC", "nombre_departamento": "Santa Cruz", "activo": True},
        {"codigo": "OR", "nombre_departamento": "Oruro", "activo": True},
        {"codigo": "PT", "nombre_departamento": "Potosí", "activo": True},
        {"codigo": "TJ", "nombre_departamento": "Tarija", "activo": True},
        {"codigo": "CH", "nombre_departamento": "Chuquisaca", "activo": True},
        {"codigo": "BE", "nombre_departamento": "Beni", "activo": True},
        {"codigo": "PD", "nombre_departamento": "Pando", "activo": True},
    ]

    insertados = 0
    for dep_data in departamentos_segip:
        # Usar SQL directo para evitar problemas de imports
        exist_check = db.execute(
            text("SELECT COUNT(*) FROM rrhh.complemento_dep WHERE codigo = :codigo"),
            {"codigo": dep_data["codigo"]}
        ).scalar()

        if not exist_check:
            db.execute(
                text("""INSERT INTO rrhh.complemento_dep (codigo, nombre_departamento, activo)
                        VALUES (:codigo, :nombre_departamento, :activo)"""),
                dep_data
            )
            insertados += 1
        else:
            print(f"  - ComplementoDep {dep_data['codigo']} ya existe, omitiendo...")

    db.commit()
    print(f"  OK: {insertados} departamentos SEGIP insertados.")


def seed_roles(db):
    """
    NIVEL 0: Insertar roles del sistema.
    Roles principales: admin, rrhh, supervisor, empleado, consulta
    """
    print("\n[NIVEL 0] Insertando roles del sistema...")

    roles_mandatorios = [
        {"nombre": "admin", "descripcion": "Administrador del sistema - acceso total", "activo": True},
        {"nombre": "rrhh", "descripcion": "Personal de RRHH - gestion de empleados", "activo": True},
        {"nombre": "supervisor", "descripcion": "Supervisor - aprueba permisos", "activo": True},
        {"nombre": "empleado", "descripcion": "Empleado - consulta su informacion", "activo": True},
        {"nombre": "consulta", "descripcion": "Solo lectura - acceso a reportes", "activo": True},
    ]

    insertados = 0
    for rol_data in roles_mandatorios:
        exist_check = db.execute(
            text("SELECT COUNT(*) FROM rrhh.rol WHERE nombre = :nombre"),
            {"nombre": rol_data["nombre"]}
        ).scalar()

        if not exist_check:
            db.execute(
                text("""INSERT INTO rrhh.rol (nombre, descripcion, activo, created_at, updated_at)
                        VALUES (:nombre, :descripcion, :activo, NOW(), NOW())"""),
                rol_data
            )
            insertados += 1
        else:
            print(f"  - Rol '{rol_data['nombre']}' ya existe, omitiendo...")

    db.commit()
    print(f"  OK: {insertados} roles insertados.")


def seed_departamentos(db):
    """NIVEL 0: Insertar estructura departamental organizacional (jerárquica)."""
    print("\n[NIVEL 0] Insertando estructura departamental organizacional...")

    # Verificar si ya existe
    exist_check = db.execute(
        text("SELECT COUNT(*) FROM rrhh.departamento WHERE codigo = 'GG'")
    ).scalar()

    if exist_check:
        print("  - Estructura ya existe, omitiendo...")
        return

    # 1. Gerencia General (raiz)
    db.execute(
        text("""INSERT INTO rrhh.departamento (nombre, codigo, id_padre, activo, created_at, updated_at)
                VALUES (:nombre, :codigo, NULL, :activo, NOW(), NOW())"""),
        {"nombre": "Gerencia General", "codigo": "GG", "activo": True}
    )
    db.flush()

    # Obtener ID de Gerencia General
    gg_id = db.execute(
        text("SELECT id FROM rrhh.departamento WHERE codigo = 'GG'")
    ).scalar()

    # 2. Gerencias de nivel 1
    gerencias = [
        {"nombre": "Gerencia de Recursos Humanos", "codigo": "RRHH"},
        {"nombre": "Gerencia Administrativa", "codigo": "ADM"},
        {"nombre": "Gerencia Comercial", "codigo": "COM"},
        {"nombre": "Gerencia de Sistemas", "codigo": "SIS"},
    ]

    for gerencia in gerencias:
        db.execute(
            text("""INSERT INTO rrhh.departamento (nombre, codigo, id_padre, activo, created_at, updated_at)
                    VALUES (:nombre, :codigo, :id_padre, TRUE, NOW(), NOW())"""),
            {"nombre": gerencia["nombre"], "codigo": gerencia["codigo"], "id_padre": gg_id}
        )
    db.flush()

    # 3. Areas bajo RRHH
    rrhh_id = db.execute(
        text("SELECT id FROM rrhh.departamento WHERE codigo = 'RRHH'")
    ).scalar()

    if rrhh_id:
        areas = [
            {"nombre": "Area de Nominas", "codigo": "RRHH-NOM"},
            {"nombre": "Area de Seleccion", "codigo": "RRHH-SEL"},
        ]
        for area in areas:
            db.execute(
                text("""INSERT INTO rrhh.departamento (nombre, codigo, id_padre, activo, created_at, updated_at)
                        VALUES (:nombre, :codigo, :id_padre, TRUE, NOW(), NOW())"""),
                {"nombre": area["nombre"], "codigo": area["codigo"], "id_padre": rrhh_id}
            )

    db.commit()
    print("  OK: Estructura departamental completada.")


def seed_decreto_incremento_salarial(db):
    """
    NIVEL 0: Insertar decreto base histórico de incremento salarial.
    Decreto Supremo 4984 / 2024 (Bolivia) vigente desde 1 de mayo de 2024.
    """
    print("\n[NIVEL 0] Insertando decreto de incremento salarial...")

    # Verificar si ya existe
    exist_check = db.execute(
        text("SELECT COUNT(*) FROM rrhh.decreto_incremento_salarial WHERE anio = 2024")
    ).scalar()

    if exist_check:
        print("  - Decreto 2024 ya existe, omitiendo...")
        return

    # Crear decreto
    db.execute(
        text("""INSERT INTO rrhh.decreto_incremento_salarial
                (anio, nuevo_smn, fecha_vigencia, referencia_decreto, created_at, updated_at)
                VALUES (:anio, :nuevo_smn, :fecha_vigencia, :referencia_decreto, NOW(), NOW())"""),
        {
            "anio": 2024,
            "nuevo_smn": Decimal("2500.00"),
            "fecha_vigencia": date(2024, 5, 1),
            "referencia_decreto": "DS 4984 / 2024"
        }
    )
    db.flush()

    # Obtener ID del decreto
    decreto_id = db.execute(
        text("SELECT id FROM rrhh.decreto_incremento_salarial WHERE anio = 2024")
    ).scalar()

    # Insertar tramos salariales
    tramos = [
        {"decreto_id": decreto_id, "orden": 1, "salario_desde": None, "salario_hasta": Decimal("2500.00"), "porcentaje": Decimal("5.00")},
        {"decreto_id": decreto_id, "orden": 2, "salario_desde": Decimal("2500.01"), "salario_hasta": Decimal("5000.00"), "porcentaje": Decimal("3.00")},
        {"decreto_id": decreto_id, "orden": 3, "salario_desde": Decimal("5000.01"), "salario_hasta": None, "porcentaje": Decimal("1.00")},
    ]

    for tramo in tramos:
        db.execute(
            text("""INSERT INTO rrhh.condicion_decreto
                    (id_decreto, orden, salario_desde, salario_hasta, porcentaje_incremento, created_at, updated_at)
                    VALUES (:decreto_id, :orden, :salario_desde, :salario_hasta, :porcentaje, NOW(), NOW())"""),
            tramo
        )

    db.commit()
    print("  OK: Decreto 2024 con 3 tramos salariales insertado.")
    print("      - Tramo 1: Hasta 2500 Bs -> 5%")
    print("      - Tramo 2: 2501 a 5000 Bs -> 3%")
    print("      - Tramo 3: Mas de 5000 Bs -> 1%")


def main():
    """Ejecutar todos los seeds del NIVEL 0."""
    print("=" * 70)
    print("SEED NIVEL 0 - DATOS BASE FUNDACIONALES")
    print("=" * 70)

    db = SessionLocal()

    try:
        seed_ci_depto_emision_ref(db)
        seed_roles(db)
        seed_departamentos(db)
        seed_decreto_incremento_salarial(db)

        print("\n" + "=" * 70)
        print("OK: SEED NIVEL 0 COMPLETADO CON EXITO")
        print("=" * 70)
        print("\nProximos pasos:")
        print("1. Ejecutar seed_nivel_1.py para crear cargo, parametro_impuesto")
        print("2. Ejecutar seed_nivel_2.py para crear empleado")
        print("3. Ejecutar seed_nivel_3.py para crear usuario, contrato, horario")
        print("\nConsulta '/scripts/orden_creacion_entidades.md' para mas detalles.")

    except Exception as e:
        print(f"\nERROR durante el seed NIVEL 0: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
