"""
Script de datos semilla (seed data) - SEMANA 1.
Carga los datos iniciales necesarios para que el sistema funcione.

EJECUTAR UNA SOLA VEZ después de aplicar las migraciones.

Uso:
    python scripts/seed_data.py
"""

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.features.auth.rol.models import Rol
from app.features.employees.departamento.models import ComplementoDep, Departamento
from app.features.employees.cargo.models import Cargo
from datetime import datetime


def seed_complementos_depto(db: Session):
    """
    Carga los 9 departamentos de Bolivia según SEGIP.
    Estos códigos se usan en el campo complemento del CI.
    """
    complementos = [
        {"codigo": "LP", "nombre_departamento": "La Paz"},
        {"codigo": "CB", "nombre_departamento": "Cochabamba"},
        {"codigo": "SC", "nombre_departamento": "Santa Cruz"},
        {"codigo": "OR", "nombre_departamento": "Oruro"},
        {"codigo": "PT", "nombre_departamento": "Potosí"},
        {"codigo": "TJ", "nombre_departamento": "Tarija"},
        {"codigo": "CH", "nombre_departamento": "Chuquisaca"},
        {"codigo": "BE", "nombre_departamento": "Beni"},
        {"codigo": "PA", "nombre_departamento": "Pando"},
    ]

    print("\n🇧🇴 Cargando departamentos Bolivia (SEGIP)...")
    for comp in complementos:
        existe = db.query(ComplementoDep).filter_by(codigo=comp["codigo"]).first()
        if not existe:
            db.add(ComplementoDep(**comp, activo=True))
            print(f"   ✓ {comp['codigo']} - {comp['nombre_departamento']}")
        else:
            print(f"   ⊘ {comp['codigo']} ya existe")

    db.commit()
    print("✅ Departamentos Bolivia cargados.\n")


def seed_roles(db: Session):
    """
    Carga los roles iniciales del sistema.
    Estos roles controlarán el acceso en la Semana 9 (JWT).
    """
    roles = [
        {
            "nombre": "admin",
            "descripcion": "Administrador del sistema - Acceso total"
        },
        {
            "nombre": "rrhh",
            "descripcion": "Personal de Recursos Humanos - Gestión de empleados y asistencia"
        },
        {
            "nombre": "supervisor",
            "descripcion": "Supervisor de área - Aprobación de permisos y justificaciones"
        },
        {
            "nombre": "empleado",
            "descripcion": "Empleado regular - Consulta de información propia"
        },
    ]

    print("👥 Cargando roles del sistema...")
    for rol_data in roles:
        existe = db.query(Rol).filter_by(nombre=rol_data["nombre"]).first()
        if not existe:
            db.add(Rol(**rol_data, activo=True))
            print(f"   ✓ {rol_data['nombre']}")
        else:
            print(f"   ⊘ {rol_data['nombre']} ya existe")

    db.commit()
    print("✅ Roles cargados.\n")


def seed_departamentos_organizacionales(db: Session):
    """
    Carga la estructura organizacional de ejemplo.
    Jerarquía básica para demostrar relaciones padre-hijo.
    """
    departamentos = [
        # Nivel 1: Dirección
        {
            "nombre": "Dirección General",
            "codigo": "DIR-GEN",
            "id_padre": None
        },
        # Nivel 2: Gerencias
        {
            "nombre": "Gerencia de Recursos Humanos",
            "codigo": "GER-RRHH",
            "id_padre": None  # Se asignará después
        },
        {
            "nombre": "Gerencia de Operaciones",
            "codigo": "GER-OPS",
            "id_padre": None
        },
        {
            "nombre": "Gerencia Administrativa y Financiera",
            "codigo": "GER-ADM",
            "id_padre": None
        },
        {
            "nombre": "Gerencia Comercial",
            "codigo": "GER-COM",
            "id_padre": None
        },
        # Nivel 3: Áreas dentro de RRHH
        {
            "nombre": "Área de Nóminas",
            "codigo": "AREA-NOM",
            "id_padre": None  # Se asignará a GER-RRHH
        },
        {
            "nombre": "Área de Reclutamiento",
            "codigo": "AREA-REC",
            "id_padre": None
        },
    ]

    print("🏢 Cargando estructura organizacional...")

    # Primera pasada: crear sin dependencias
    dir_gen = db.query(Departamento).filter_by(codigo="DIR-GEN").first()
    if not dir_gen:
        dir_gen = Departamento(
            nombre="Dirección General",
            codigo="DIR-GEN",
            id_padre=None,
            activo=True
        )
        db.add(dir_gen)
        db.commit()
        db.refresh(dir_gen)
        print(f"   ✓ Dirección General (ID: {dir_gen.id})")
    else:
        print(f"   ⊘ Dirección General ya existe (ID: {dir_gen.id})")

    # Gerencias bajo Dirección General
    gerencias = [
        ("Gerencia de Recursos Humanos", "GER-RRHH"),
        ("Gerencia de Operaciones", "GER-OPS"),
        ("Gerencia Administrativa y Financiera", "GER-ADM"),
        ("Gerencia Comercial", "GER-COM"),
    ]

    ger_rrhh = None
    for nombre, codigo in gerencias:
        existe = db.query(Departamento).filter_by(codigo=codigo).first()
        if not existe:
            ger = Departamento(
                nombre=nombre,
                codigo=codigo,
                id_padre=dir_gen.id,
                activo=True
            )
            db.add(ger)
            db.commit()
            db.refresh(ger)
            print(f"   ✓ {nombre} (ID: {ger.id})")
            if codigo == "GER-RRHH":
                ger_rrhh = ger
        else:
            print(f"   ⊘ {nombre} ya existe (ID: {existe.id})")
            if codigo == "GER-RRHH":
                ger_rrhh = existe

    # Áreas bajo RRHH
    if ger_rrhh:
        areas = [
            ("Área de Nóminas", "AREA-NOM"),
            ("Área de Reclutamiento", "AREA-REC"),
        ]

        for nombre, codigo in areas:
            existe = db.query(Departamento).filter_by(codigo=codigo).first()
            if not existe:
                area = Departamento(
                    nombre=nombre,
                    codigo=codigo,
                    id_padre=ger_rrhh.id,
                    activo=True
                )
                db.add(area)
                db.commit()
                db.refresh(area)
                print(f"   ✓ {nombre} (ID: {area.id})")
            else:
                print(f"   ⊘ {nombre} ya existe (ID: {existe.id})")

    print("✅ Estructura organizacional cargada.\n")


def seed_cargos(db: Session):
    """
    Carga cargos de ejemplo en cada departamento.
    Incluye cargos de confianza (exentos de marcación).
    """
    print("💼 Cargando cargos...")

    # Obtener departamentos
    dir_gen = db.query(Departamento).filter_by(codigo="DIR-GEN").first()
    ger_rrhh = db.query(Departamento).filter_by(codigo="GER-RRHH").first()
    ger_ops = db.query(Departamento).filter_by(codigo="GER-OPS").first()
    area_nom = db.query(Departamento).filter_by(codigo="AREA-NOM").first()

    if not dir_gen or not ger_rrhh:
        print("⚠️  Departamentos no encontrados. Ejecuta seed_departamentos primero.")
        return

    cargos = [
        # Dirección General (cargos de confianza)
        {
            "nombre": "Director General",
            "codigo": "DIR-001",
            "nivel": 1,
            "es_cargo_confianza": True,
            "id_departamento": dir_gen.id
        },
        # Gerencia RRHH
        {
            "nombre": "Gerente de RRHH",
            "codigo": "GER-RRHH-001",
            "nivel": 2,
            "es_cargo_confianza": True,
            "id_departamento": ger_rrhh.id
        },
        {
            "nombre": "Jefe de Nóminas",
            "codigo": "JEFE-NOM-001",
            "nivel": 3,
            "es_cargo_confianza": False,
            "id_departamento": area_nom.id if area_nom else ger_rrhh.id
        },
        {
            "nombre": "Asistente de RRHH",
            "codigo": "ASIST-RRHH-001",
            "nivel": 4,
            "es_cargo_confianza": False,
            "id_departamento": ger_rrhh.id
        },
        # Gerencia Operaciones
        {
            "nombre": "Gerente de Operaciones",
            "codigo": "GER-OPS-001",
            "nivel": 2,
            "es_cargo_confianza": True,
            "id_departamento": ger_ops.id if ger_ops else dir_gen.id
        },
        {
            "nombre": "Supervisor de Producción",
            "codigo": "SUP-PROD-001",
            "nivel": 3,
            "es_cargo_confianza": False,
            "id_departamento": ger_ops.id if ger_ops else dir_gen.id
        },
        {
            "nombre": "Operario",
            "codigo": "OPER-001",
            "nivel": 5,
            "es_cargo_confianza": False,
            "id_departamento": ger_ops.id if ger_ops else dir_gen.id
        },
    ]

    for cargo_data in cargos:
        existe = db.query(Cargo).filter_by(codigo=cargo_data["codigo"]).first()
        if not existe:
            cargo = Cargo(**cargo_data, activo=True)
            db.add(cargo)
            confianza = "🔑 Confianza" if cargo_data["es_cargo_confianza"] else ""
            print(f"   ✓ {cargo_data['nombre']} {confianza}")
        else:
            print(f"   ⊘ {cargo_data['nombre']} ya existe")

    db.commit()
    print("✅ Cargos cargados.\n")


def main():
    """
    Ejecuta todos los scripts de seed en orden.
    """
    print("=" * 60)
    print("🌱 INICIANDO CARGA DE DATOS SEMILLA - SEMANA 1")
    print("=" * 60)

    db = SessionLocal()

    try:
        seed_complementos_depto(db)
        seed_roles(db)
        seed_departamentos_organizacionales(db)
        seed_cargos(db)

        print("=" * 60)
        print("✅ DATOS SEMILLA CARGADOS EXITOSAMENTE")
        print("=" * 60)
        print("\n📊 Resumen:")
        print(f"   • Departamentos Bolivia: {db.query(ComplementoDep).count()}")
        print(f"   • Roles: {db.query(Rol).count()}")
        print(f"   • Departamentos organizacionales: {db.query(Departamento).count()}")
        print(f"   • Cargos: {db.query(Cargo).count()}")
        print("\n🚀 El sistema está listo para usarse.\n")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
