"""seed_parametros_impuesto_afp

Siembra las tasas AFP que faltaban en rrhh.parametro_impuesto.

Antes de esta migración la tabla tenía UNA sola fila (RC_IVA 13% desde
1992-01-01). Como la vista rrhh.v_saldo_impuestos_planilla hace
COALESCE(afp.porcentaje, 0), los reportes de planilla venían calculando 0% de
AFP laboral en silencio y el salario_neto_estimado salía inflado.

RC_IVA NO se toca: la fila de producción arranca en 1992-01-01 y el archivo de
referencia dice 2000-01-01 — el dato desplegado manda.

VALORES Y FUENTES
-----------------
Los valores base salen de InformacionContexto/codigoPostgresSQL.txt:1419-1426,
con dos correcciones respecto de ese archivo:

1. AFP_PATRONAL_SOLIDARIO: el archivo dice 3.00%. La Ley N° 1582 del 01/10/2024
   lo subió a 3.50%, y la RA APS/DJ/DP/N° 1377/2024 del 11/10/2024 dispuso
   aplicar los nuevos porcentajes desde la planilla de octubre 2024, con
   regularización de lo ya pagado. Por eso se siembran DOS filas: 3.00% cerrado
   el 2024-09-30 y 3.50% vigente desde 2024-10-01.

2. AFP_PATRONAL_VIVIENDA: el archivo dice 3.00%, que parece haber duplicado por
   error el valor del solidario. El desglose del 16.71% patronal boliviano es
   10% CNS + 2% Pro-Vivienda + 1.71% riesgo profesional + 3% solidario patronal.
   Se siembra 2.00%.

ADVERTENCIA: los dos valores PATRONAL están respaldados por fuentes públicas
consistentes, pero PENDIENTES DE VALIDACIÓN FORMAL con la Gestora Pública de la
Seguridad Social de Largo Plazo o un contador/abogado laboral boliviano antes de
usarse en un caso real. La advertencia también viaja en la columna `descripcion`
de esas filas, que es lo que muestra la pantalla de impuestos.

EFECTO COLATERAL: sembrar AFP_LABORAL 12.71% CAMBIA los números de los reportes
de planilla (hoy descuenta 0%). Ojo que esto NO deja la planilla correcta: la
base imponible del RC-IVA sigue mal calculada (no descuenta los 2 SMN ni el
aporte AFP). Ver la sección de severidad ALTA en CLAUDE.md.

Revision ID: b8e5d1a04c73
Revises: a7f4c2e8b310
Create Date: 2026-08-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8e5d1a04c73'
down_revision: Union[str, None] = 'a7f4c2e8b310'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_PENDIENTE = (
    "Respaldado por fuentes publicas consistentes; pendiente de validacion "
    "formal con la Gestora Publica o un contador/abogado laboral boliviano."
)

# (nombre, tipo_aporte, porcentaje, inicio, fin, descripcion)
#
# El solidario va en DOS filas a propósito: refleja la historia real del
# concepto y de paso deja la sección de historial de la pantalla con datos
# desde el día uno. El cierre en 2024-09-30 es exactamente 2024-10-01 menos un
# día, la misma regla que aplica create_parametro_impuesto.
PARAMETROS = [
    (
        "AFP_LABORAL", "LABORAL", "12.71", "2003-01-01", None,
        "Aporte del empleado: pension (10%) + prima de riesgo (1.71%) + comision "
        "AFP y aporte solidario. Base: Ley 065 de Pensiones.",
    ),
    (
        "AFP_PATRONAL_VIVIENDA", "PATRONAL", "2.00", "2003-01-01", None,
        "Aporte patronal a Pro-Vivienda sobre salario bruto. Lo paga la empresa, "
        "no se descuenta al empleado. " + _PENDIENTE,
    ),
    (
        "AFP_PATRONAL_SOLIDARIO", "PATRONAL", "3.00", "2010-01-01", "2024-09-30",
        "Aporte solidario patronal, tasa vigente hasta la Ley 1582. Lo paga la "
        "empresa, no se descuenta al empleado. " + _PENDIENTE,
    ),
    (
        "AFP_PATRONAL_SOLIDARIO", "PATRONAL", "3.50", "2024-10-01", None,
        "Aporte solidario patronal elevado de 3% a 3.5% por la Ley 1582 del "
        "01/10/2024; RA APS/DJ/DP/N 1377/2024 del 11/10/2024 lo aplica desde la "
        "planilla de octubre 2024. Lo paga la empresa. " + _PENDIENTE,
    ),
]


def upgrade() -> None:
    """Inserta las 4 filas que falten, sin tocar las que ya existan."""
    conn = op.get_bind()

    # La guarda de idempotencia va por (nombre, fecha_vigencia_inicio) y NO por
    # nombre solo: AFP_PATRONAL_SOLIDARIO tiene dos filas legítimas con el mismo
    # nombre. Un WHERE NOT EXISTS por nombre sembraría la de 3.00% y descartaría
    # la de 3.50% EN SILENCIO, dejando el sistema con la tasa previa a la Ley
    # 1582 como vigente — justo la corrección que esta migración aporta.
    #
    # created_at/updated_at se fijan explícitamente: son default=datetime.now
    # del lado Python, SIN server_default, y las columnas son NOT NULL, así que
    # un INSERT en SQL crudo que las omita falla.
    sql = sa.text(
        """
        INSERT INTO rrhh.parametro_impuesto
            (nombre, tipo_aporte, porcentaje, fecha_vigencia_inicio,
             fecha_vigencia_fin, descripcion, created_at, updated_at)
        SELECT :nombre, :tipo_aporte, CAST(:porcentaje AS numeric(5,2)),
               CAST(:inicio AS date), CAST(:fin AS date), :descripcion,
               NOW(), NOW()
        WHERE NOT EXISTS (
            SELECT 1 FROM rrhh.parametro_impuesto
            WHERE nombre = :nombre
              AND fecha_vigencia_inicio = CAST(:inicio AS date)
        )
        """
    )

    for nombre, tipo, porcentaje, inicio, fin, descripcion in PARAMETROS:
        resultado = conn.execute(sql, {
            "nombre": nombre,
            "tipo_aporte": tipo,
            "porcentaje": porcentaje,
            "inicio": inicio,
            "fin": fin,
            "descripcion": descripcion,
        })
        estado = "insertado" if resultado.rowcount else "ya existia, sin cambios"
        print(f"[parametro_impuesto] {nombre} desde {inicio} ({porcentaje}%): {estado}")


def downgrade() -> None:
    """Borra sólo las 4 filas que sembró upgrade, por (nombre, fecha_inicio)."""
    conn = op.get_bind()

    sql = sa.text(
        """
        DELETE FROM rrhh.parametro_impuesto
        WHERE nombre = :nombre
          AND fecha_vigencia_inicio = CAST(:inicio AS date)
        """
    )

    for nombre, _tipo, _porcentaje, inicio, _fin, _descripcion in PARAMETROS:
        resultado = conn.execute(sql, {"nombre": nombre, "inicio": inicio})
        print(f"[parametro_impuesto] {nombre} desde {inicio}: {resultado.rowcount} fila(s) borrada(s)")
