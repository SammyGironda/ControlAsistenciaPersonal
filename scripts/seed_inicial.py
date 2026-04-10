"""
Script de datos semilla para Semana 1-2.
Inserta datos iniciales en las tablas:
- complemento_dep (departamentos de Bolivia)
- rol (roles del sistema)
- departamento (departamentos organizacionales)
- cargo (cargos de la empresa)
- usuario (usuario admin inicial - Semana 2)
"""

import sys
from pathlib import Path

# Agregar el directorio raíz al path para importar los modelos
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import SessionLocal, engine
from app.db.base import Base
from app.features.auth.rol.models import Rol
from app.features.auth.usuario.models import Usuario
from app.features.employees.empleado.models import Empleado
from app.features.employees.departamento.models import Departamento, ComplementoDep
from app.features.employees.cargo.models import Cargo


def seed_complemento_dep(db):
    """Insertar códigos de departamento de Bolivia (SEGIP)."""
    print("→ Insertando complementos de departamento (SEGIP)...")

    departamentos_bolivia = [
        {"codigo": "LP", "nombre_departamento": "La Paz", "activo": True},
        {"codigo": "CB", "nombre_departamento": "Cochabamba", "activo": True},
        {"codigo": "SC", "nombre_departamento": "Santa Cruz", "activo": True},
        {"codigo": "OR", "nombre_departamento": "Oruro", "activo": True},
        {"codigo": "PT", "nombre_departamento": "Potosí", "activo": True},
        {"codigo": "TJ", "nombre_departamento": "Tarija", "activo": True},
        {"codigo": "CH", "nombre_departamento": "Chuquisaca", "activo": True},
        {"codigo": "BE", "nombre_departamento": "Beni", "activo": True},
        {"codigo": "PA", "nombre_departamento": "Pando", "activo": True},
    ]

    for dep_data in departamentos_bolivia:
        # Verificar si ya existe
        existe = db.query(ComplementoDep).filter_by(codigo=dep_data["codigo"]).first()
        if not existe:
            dep = ComplementoDep(**dep_data)
            db.add(dep)

    db.commit()
    print("✓ Complementos de departamento insertados.")


def seed_roles(db):
    """Insertar roles del sistema."""
    print("→ Insertando roles del sistema...")

    roles = [
        {
            "nombre": "admin",
            "descripcion": "Administrador del sistema - acceso total",
            "activo": True
        },
        {
            "nombre": "rrhh",
            "descripcion": "Personal de Recursos Humanos - gestión de empleados y asistencia",
            "activo": True
        },
        {
            "nombre": "supervisor",
            "descripcion": "Supervisor de área - aprueba permisos y justificaciones",
            "activo": True
        },
        {
            "nombre": "empleado",
            "descripcion": "Empleado - consulta su propia información",
            "activo": True
        },
        {
            "nombre": "consulta",
            "descripcion": "Solo lectura - acceso a reportes",
            "activo": True
        },
    ]

    for rol_data in roles:
        # Verificar si ya existe
        existe = db.query(Rol).filter_by(nombre=rol_data["nombre"]).first()
        if not existe:
            rol = Rol(**rol_data)
            db.add(rol)

    db.commit()
    print("✓ Roles insertados.")


def seed_departamentos(db):
    """Insertar departamentos organizacionales (estructura jerárquica)."""
    print("→ Insertando departamentos organizacionales...")

    # Gerencia General
    gerencia_general = db.query(Departamento).filter_by(codigo="GG").first()
    if not gerencia_general:
        gerencia_general = Departamento(
            nombre="Gerencia General",
            codigo="GG",
            id_padre=None,
            activo=True
        )
        db.add(gerencia_general)
        db.commit()
        db.refresh(gerencia_general)

    # Gerencias bajo Gerencia General
    gerencias = [
        {"nombre": "Gerencia de Recursos Humanos", "codigo": "RRHH", "id_padre": gerencia_general.id},
        {"nombre": "Gerencia Administrativa", "codigo": "ADM", "id_padre": gerencia_general.id},
        {"nombre": "Gerencia Comercial", "codigo": "COM", "id_padre": gerencia_general.id},
        {"nombre": "Gerencia de Sistemas", "codigo": "SIS", "id_padre": gerencia_general.id},
    ]

    for gerencia_data in gerencias:
        existe = db.query(Departamento).filter_by(codigo=gerencia_data["codigo"]).first()
        if not existe:
            gerencia = Departamento(**gerencia_data)
            db.add(gerencia)

    db.commit()

    # Áreas bajo RRHH
    rrhh = db.query(Departamento).filter_by(codigo="RRHH").first()
    if rrhh:
        areas_rrhh = [
            {"nombre": "Área de Nóminas", "codigo": "RRHH-NOM", "id_padre": rrhh.id},
            {"nombre": "Área de Selección", "codigo": "RRHH-SEL", "id_padre": rrhh.id},
        ]
        for area_data in areas_rrhh:
            existe = db.query(Departamento).filter_by(codigo=area_data["codigo"]).first()
            if not existe:
                area = Departamento(**area_data)
                db.add(area)

    db.commit()
    print("Departamentos organizacionales insertados.")


def seed_cargos(db):
    """Insertar cargos iniciales."""
    print("→ Insertando cargos...")

    # Obtener IDs de departamentos
    gg = db.query(Departamento).filter_by(codigo="GG").first()
    rrhh = db.query(Departamento).filter_by(codigo="RRHH").first()
    adm = db.query(Departamento).filter_by(codigo="ADM").first()
    sis = db.query(Departamento).filter_by(codigo="SIS").first()

    if not all([gg, rrhh, adm, sis]):
        print("No se encontraron todos los departamentos. Primero ejecuta seed_departamentos.")
        return

    cargos = [
        # Gerencia General
        {"nombre": "Gerente General", "codigo": "C-GG-01", "nivel": 1,
         "es_cargo_confianza": True, "id_departamento": gg.id},

        # RRHH
        {"nombre": "Gerente de RRHH", "codigo": "C-RRHH-01", "nivel": 2,
         "es_cargo_confianza": True, "id_departamento": rrhh.id},
        {"nombre": "Analista de Nóminas", "codigo": "C-RRHH-02", "nivel": 4,
         "es_cargo_confianza": False, "id_departamento": rrhh.id},
        {"nombre": "Asistente RRHH", "codigo": "C-RRHH-03", "nivel": 5,
         "es_cargo_confianza": False, "id_departamento": rrhh.id},

        # Administrativo
        {"nombre": "Gerente Administrativo", "codigo": "C-ADM-01", "nivel": 2,
         "es_cargo_confianza": True, "id_departamento": adm.id},
        {"nombre": "Contador", "codigo": "C-ADM-02", "nivel": 4,
         "es_cargo_confianza": False, "id_departamento": adm.id},

        # Sistemas
        {"nombre": "Gerente de Sistemas", "codigo": "C-SIS-01", "nivel": 2,
         "es_cargo_confianza": True, "id_departamento": sis.id},
        {"nombre": "Desarrollador Senior", "codigo": "C-SIS-02", "nivel": 3,
         "es_cargo_confianza": False, "id_departamento": sis.id},
        {"nombre": "Desarrollador Junior", "codigo": "C-SIS-03", "nivel": 5,
         "es_cargo_confianza": False, "id_departamento": sis.id},
    ]

    for cargo_data in cargos:
        existe = db.query(Cargo).filter_by(codigo=cargo_data["codigo"]).first()
        if not existe:
            cargo = Cargo(**cargo_data)
            db.add(cargo)

    db.commit()
    print("✓ Cargos insertados.")


def seed_usuarios(db):
    """Insertar usuario administrador inicial (Semana 2)."""
    print("→ Insertando usuario administrador...")

    # Buscar el rol admin
    rol_admin = db.query(Rol).filter_by(nombre="admin").first()
    if not rol_admin:
        print("❌ No se encontró el rol 'admin'. Primero ejecuta seed_roles.")
        return

    # Verificar si ya existe un usuario admin
    usuario_admin = db.query(Usuario).filter_by(username="admin").first()
    if usuario_admin:
        print("ℹ Usuario 'admin' ya existe. Omitiendo.")
        return

    # Crear usuario admin
    usuario = Usuario(
        username="admin",
        id_rol=rol_admin.id,
        id_empleado=None,  # Usuario admin no está vinculado a un empleado
        activo=True
    )
    usuario.set_password("admin123")  # Contraseña inicial, cambiar en producción

    db.add(usuario)
    db.commit()

    print("✓ Usuario administrador creado.")
    print("  Username: admin")
    print("  Password: admin123")
    print("  ⚠ IMPORTANTE: Cambiar la contraseña en producción")


def main():
    """Ejecutar todos los seeds."""
    print("=" * 60)
    print("SEED INICIAL - SEMANA 1-2")
    print("=" * 60)

    # Crear sesión
    db = SessionLocal()

    try:
        seed_complemento_dep(db)
        seed_roles(db)
        seed_usuarios(db)  # Nuevo en Semana 2
        seed_departamentos(db)
        seed_cargos(db)

        print("\n" + "=" * 60)
        print("✅ SEED COMPLETADO CON ÉXITO")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ ERROR durante el seed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
