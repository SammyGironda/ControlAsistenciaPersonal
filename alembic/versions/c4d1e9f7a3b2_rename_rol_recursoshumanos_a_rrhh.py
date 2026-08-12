"""Renombra el rol id=2 de 'RecursosHumanos' a 'rrhh'

Todo el código compara los roles contra el literal 'rrhh'
(require_roles("admin", "rrhh") en ~15 routers, más ROLES_GESTORES /
ROLES_LECTURA_TOTAL / ROLES_APROBADORES en app/core/deps.py). En Neon el rol
id=2 quedó cargado como 'RecursosHumanos', así que ningún usuario con ese rol
pasaría ninguno de esos guards: recibiría 403 en todo el sistema.

Se corrige el dato en vez del código: es una fila contra 15+ llamadas repartidas
por todos los módulos, y deja la base alineada con los seeds de scripts/, que ya
insertan 'rrhh'.

Verificación previa (solo lectura, 2026-08-12):
- roles en producción: admin(1), RecursosHumanos(2), supervisor(3), empleado(4),
  consulta(5). Ninguna fila usa ya el nombre 'rrhh', así que el UNIQUE
  uq_rol_nombre no choca.
- 0 usuarios con id_rol=2, por lo que el rename no afecta ninguna sesión activa.
  get_current_user además relee el rol de la base en cada request, sin confiar en
  el claim nombre_rol del token.

Revision ID: c4d1e9f7a3b2
Revises: 3d9a17c4b8e2
Create Date: 2026-08-12

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c4d1e9f7a3b2'
down_revision = '3d9a17c4b8e2'
branch_labels = None
depends_on = None


ID_ROL_RRHH = 2
NOMBRE_VIEJO = 'RecursosHumanos'
NOMBRE_NUEVO = 'rrhh'


def _renombrar(desde: str, hacia: str) -> None:
    """
    Renombra el rol ID_ROL_RRHH, filtrando por id y no por nombre.

    El id es el criterio estable: si alguien ya tocó el nombre por otra vía, un
    UPDATE ... WHERE nombre = 'RecursosHumanos' apuntaría a la fila equivocada o a
    ninguna sin que se note. El nombre se usa sólo como guarda de idempotencia.
    """
    conn = op.get_bind()

    # rrhh.rol tiene UNIQUE (nombre): si otra fila ya ocupa el nombre destino, el
    # UPDATE reventaría con un IntegrityError críptico. Mejor fallar explicando qué
    # pasa y qué hacer.
    ocupado = conn.execute(
        sa.text("SELECT id FROM rrhh.rol WHERE nombre = :nombre AND id <> :id"),
        {"nombre": hacia, "id": ID_ROL_RRHH},
    ).scalar()

    if ocupado is not None:
        raise RuntimeError(
            f"No se puede renombrar el rol id={ID_ROL_RRHH} a '{hacia}': el rol "
            f"id={ocupado} ya usa ese nombre (uq_rol_nombre). Consolidar ambos roles "
            "a mano — reasignando los usuarios de uno al otro — antes de correr esta "
            "migración."
        )

    # rrhh.rol no tiene trigger de updated_at (discrepancia #11 de CLAUDE.md) y el
    # onupdate=datetime.now de SQLAlchemy no corre en SQL crudo: se fija a mano.
    # NOW() es lo que usa rrhh.fn_set_updated_at(), creada en 122bc6566cae.
    resultado = conn.execute(
        sa.text(
            """
            UPDATE rrhh.rol
            SET nombre = :hacia,
                updated_at = NOW()
            WHERE id = :id
              AND nombre = :desde
            """
        ),
        {"hacia": hacia, "desde": desde, "id": ID_ROL_RRHH},
    )

    if resultado.rowcount == 0:
        print(
            f"  [rol id={ID_ROL_RRHH}] sin cambios: no estaba en '{desde}'. "
            "Probablemente ya fue renombrado."
        )
    else:
        print(f"  [rol id={ID_ROL_RRHH}] '{desde}' -> '{hacia}'")


def upgrade() -> None:
    _renombrar(NOMBRE_VIEJO, NOMBRE_NUEVO)


def downgrade() -> None:
    _renombrar(NOMBRE_NUEVO, NOMBRE_VIEJO)
