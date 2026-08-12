"""
Cobertura de `calcular_horas_habiles_rango` y `asegurar_vacacion_gestion`.

Son las dos piezas que permiten al frontend mostrar el costo real de una
solicitud antes de crearla: hasta ahora `detalle_vacacion.horas_habiles` lo
estimaba el cliente a mano y `rrhh.vacacion` estaba prácticamente vacía.

Tests unitarios con dobles y `monkeypatch`, como el resto de la suite: no se
levanta base de datos. Las dos queries pesadas (feriados y asignaciones de
horario) se sustituyen por sus helpers monkeypatcheados.

Fechas de referencia (agosto 2026):
    17=lun  19=mie  21=vie  22=sab  23=dom
"""

from datetime import date, time
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.features.attendance.vacaciones import services


# ===== DOBLES =====

class FakeQuery:
    def __init__(self, resultado):
        self._resultado = resultado

    def options(self, *_args, **_kwargs):
        return self

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def first(self):
        return self._resultado


class FakeDb:
    """
    Devuelve un resultado distinto según el modelo consultado. `escalares` es la
    cola de valores que va devolviendo `db.execute(...).scalar()` (la llamada a
    rrhh.fn_horas_vacacion_lgt).
    """

    def __init__(self, por_modelo=None, escalares=None):
        self.por_modelo = por_modelo or {}
        self.escalares = list(escalares or [])
        self.agregados = []
        self.commits = 0
        self.rollbacks = 0

    def query(self, modelo):
        return FakeQuery(self.por_modelo.get(modelo.__name__))

    def execute(self, *_args, **_kwargs):
        valor = self.escalares.pop(0) if self.escalares else None
        return SimpleNamespace(scalar=lambda: valor)

    def add(self, obj):
        self.agregados.append(obj)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def refresh(self, _obj):
        pass


def _empleado(id=3, complemento_dep="LP", fecha_ingreso=date(2020, 1, 15)):
    return SimpleNamespace(
        id=id,
        complemento_dep=complemento_dep,
        fecha_ingreso=fecha_ingreso,
    )


def _horario(
    id=1,
    entrada=time(8, 0),
    salida=time(16, 0),
    dias=(1, 2, 3, 4, 5),
    semanal=None,
):
    """Por defecto: lunes a viernes, 8h de jornada. `dias` usa 1=lunes..7=domingo."""
    return SimpleNamespace(
        id=id,
        hora_entrada=entrada,
        hora_salida=salida,
        dias_laborables=list(dias) if isinstance(dias, (list, tuple)) else dias,
        jornada_semanal_horas=semanal,
    )


def _asignacion(horario, inicio=date(2020, 1, 1), fin=None):
    return SimpleNamespace(horario=horario, fecha_inicio=inicio, fecha_fin=fin)


# Centinela: `empleado=None` es un caso de prueba real (empleado inexistente),
# así que no sirve como valor por defecto del parámetro.
_POR_DEFECTO = object()


def _calcular(monkeypatch, inicio, fin, asignaciones, feriados=None, empleado=_POR_DEFECTO):
    monkeypatch.setattr(
        services, "_asignaciones_en_rango", lambda *_a, **_k: asignaciones
    )
    monkeypatch.setattr(
        services, "_feriados_en_rango", lambda *_a, **_k: feriados or {}
    )

    db = FakeDb(por_modelo={
        "Empleado": _empleado() if empleado is _POR_DEFECTO else empleado
    })

    return services.calcular_horas_habiles_rango(db, 3, inicio, fin)


# ===== CÁLCULO DE HORAS HÁBILES =====

def test_semana_laboral_completa(monkeypatch):
    """Lunes a viernes con jornada de 8h: 5 días, 40h, nada excluido."""
    resultado = _calcular(
        monkeypatch, date(2026, 8, 17), date(2026, 8, 21), [_asignacion(_horario())]
    )

    assert resultado.dias_calendario == 5
    assert resultado.dias_habiles == 5
    assert resultado.horas_habiles == Decimal("40.0")
    assert resultado.horas_por_jornada == Decimal("8.0")
    assert resultado.horario_uniforme is True
    assert resultado.dias_excluidos == []


def test_fin_de_semana_no_suma_horas(monkeypatch):
    """Extender el rango al sábado y domingo no cambia el total."""
    resultado = _calcular(
        monkeypatch, date(2026, 8, 17), date(2026, 8, 23), [_asignacion(_horario())]
    )

    assert resultado.dias_calendario == 7
    assert resultado.dias_habiles == 5
    assert resultado.horas_habiles == Decimal("40.0")
    assert [d.fecha for d in resultado.dias_excluidos] == [
        date(2026, 8, 22),
        date(2026, 8, 23),
    ]
    assert {d.motivo.value for d in resultado.dias_excluidos} == {"descanso"}
    assert [d.etiqueta for d in resultado.dias_excluidos] == ["Sábado", "Domingo"]


def test_feriado_en_dia_laborable_se_descuenta(monkeypatch):
    """Un feriado entre semana resta un día hábil y se reporta con su descripción."""
    resultado = _calcular(
        monkeypatch,
        date(2026, 8, 17),
        date(2026, 8, 21),
        [_asignacion(_horario())],
        feriados={date(2026, 8, 19): "Día de prueba"},
    )

    assert resultado.dias_habiles == 4
    assert resultado.horas_habiles == Decimal("32.0")
    assert len(resultado.dias_excluidos) == 1

    excluido = resultado.dias_excluidos[0]
    assert excluido.fecha == date(2026, 8, 19)
    assert excluido.motivo.value == "feriado"
    assert excluido.etiqueta == "Día de prueba"


def test_feriado_en_sabado_no_se_cuenta_dos_veces(monkeypatch):
    """
    Descanso tiene precedencia sobre feriado, igual que en calcular_asistencia_dia.
    Un feriado en sábado aparece UNA vez y como descanso, no dos.
    """
    resultado = _calcular(
        monkeypatch,
        date(2026, 8, 17),
        date(2026, 8, 23),
        [_asignacion(_horario())],
        feriados={date(2026, 8, 22): "Feriado en sábado"},
    )

    assert resultado.dias_habiles == 5
    assert resultado.horas_habiles == Decimal("40.0")

    del_sabado = [d for d in resultado.dias_excluidos if d.fecha == date(2026, 8, 22)]
    assert len(del_sabado) == 1
    assert del_sabado[0].motivo.value == "descanso"


def test_rango_solo_de_fin_de_semana_da_cero(monkeypatch):
    """
    Elegir solo sábado y domingo devuelve 0 horas, NO un error: el frontend
    necesita el 0 para explicar por qué no puede enviar la solicitud.
    """
    resultado = _calcular(
        monkeypatch, date(2026, 8, 15), date(2026, 8, 16), [_asignacion(_horario())]
    )

    assert resultado.dias_habiles == 0
    assert resultado.horas_habiles == Decimal("0.0")
    assert len(resultado.dias_excluidos) == 2


def test_dias_laborables_en_formato_string(monkeypatch):
    """`dias_laborables` puede venir como 'L-V'; lo resuelve _parse_dias_laborables."""
    resultado = _calcular(
        monkeypatch,
        date(2026, 8, 17),
        date(2026, 8, 23),
        [_asignacion(_horario(dias="L-V"))],
    )

    assert resultado.dias_habiles == 5
    assert resultado.horas_habiles == Decimal("40.0")


def test_sabado_laborable_suma(monkeypatch):
    """Un horario que incluye el sábado (1..6) sí lo cuenta."""
    resultado = _calcular(
        monkeypatch,
        date(2026, 8, 17),
        date(2026, 8, 23),
        [_asignacion(_horario(dias=(1, 2, 3, 4, 5, 6)))],
    )

    assert resultado.dias_habiles == 6
    assert resultado.horas_habiles == Decimal("48.0")
    assert [d.fecha for d in resultado.dias_excluidos] == [date(2026, 8, 23)]


def test_cambio_de_horario_dentro_del_rango(monkeypatch):
    """
    La asignación se resuelve POR FECHA, no una vez para todo el rango. Con dos
    jornadas distintas, horario_uniforme es False y el total las mezcla.
    """
    viejo = _horario(id=1, entrada=time(8, 0), salida=time(16, 0))          # 8h
    nuevo = _horario(id=2, entrada=time(8, 0), salida=time(12, 0))          # 4h

    asignaciones = [
        # ordenadas por fecha_inicio DESC, como las devuelve _asignaciones_en_rango
        _asignacion(nuevo, inicio=date(2026, 8, 19)),
        _asignacion(viejo, inicio=date(2020, 1, 1), fin=date(2026, 8, 18)),
    ]

    resultado = _calcular(
        monkeypatch, date(2026, 8, 17), date(2026, 8, 21), asignaciones
    )

    # lun+mar a 8h = 16, mie+jue+vie a 4h = 12
    assert resultado.dias_habiles == 5
    assert resultado.horas_habiles == Decimal("28.0")
    assert resultado.horario_uniforme is False
    assert resultado.horas_por_jornada == Decimal("8.0")  # la del primer día


def test_dias_sin_horario_se_reportan_sin_cortar(monkeypatch):
    """
    Si solo a algunas fechas les falta horario vigente, se excluyen y el cálculo
    sigue: no se corta todo el rango.
    """
    asignaciones = [_asignacion(_horario(), inicio=date(2026, 8, 19))]

    resultado = _calcular(
        monkeypatch, date(2026, 8, 17), date(2026, 8, 21), asignaciones
    )

    sin_horario = [d for d in resultado.dias_excluidos if d.motivo.value == "sin_horario"]
    assert [d.fecha for d in sin_horario] == [date(2026, 8, 17), date(2026, 8, 18)]
    assert resultado.dias_habiles == 3
    assert resultado.horas_habiles == Decimal("24.0")


def test_sin_ningun_horario_en_el_rango_es_400(monkeypatch):
    """
    Si NINGUNA fecha tiene horario, el problema es la asignación faltante y no el
    rango: se corta con un mensaje accionable en vez de devolver 0 horas.
    """
    with pytest.raises(HTTPException) as exc:
        _calcular(monkeypatch, date(2026, 8, 17), date(2026, 8, 21), [])

    assert exc.value.status_code == 400
    assert "no tiene horario asignado" in exc.value.detail


def test_fecha_fin_anterior_a_inicio_es_400(monkeypatch):
    with pytest.raises(HTTPException) as exc:
        _calcular(
            monkeypatch, date(2026, 8, 21), date(2026, 8, 17), [_asignacion(_horario())]
        )

    assert exc.value.status_code == 400
    assert "fecha_fin" in exc.value.detail


def test_rango_demasiado_largo_es_400(monkeypatch):
    with pytest.raises(HTTPException) as exc:
        _calcular(
            monkeypatch, date(2026, 1, 1), date(2027, 12, 31), [_asignacion(_horario())]
        )

    assert exc.value.status_code == 400
    assert "máximo" in exc.value.detail


def test_empleado_inexistente_es_404(monkeypatch):
    with pytest.raises(HTTPException) as exc:
        _calcular(
            monkeypatch,
            date(2026, 8, 17),
            date(2026, 8, 21),
            [_asignacion(_horario())],
            empleado=None,
        )

    assert exc.value.status_code == 404


# ===== DERIVACIÓN DE LAS HORAS POR JORNADA =====

def test_jornada_desde_entrada_y_salida():
    assert services._horas_por_jornada(
        _horario(entrada=time(8, 30), salida=time(16, 30))
    ) == Decimal("8.0")


def test_jornada_desde_jornada_semanal():
    """Sin hora_entrada/salida (jornada discontinua) se usa semanal / días."""
    horario = _horario(entrada=None, salida=None, dias=(1, 2, 3, 4, 5), semanal=Decimal("40.0"))

    assert services._horas_por_jornada(horario) == Decimal("8.0")


def test_jornada_cae_al_fallback():
    """Sin horas ni jornada semanal, 8.0."""
    horario = _horario(entrada=None, salida=None, semanal=None)

    assert services._horas_por_jornada(horario) == services.HORAS_JORNADA_FALLBACK


def test_turno_que_cruza_medianoche_no_resta_horas():
    """
    salida <= entrada daría una jornada negativa. Cae al siguiente criterio en
    vez de restar horas del total.
    """
    horario = _horario(
        entrada=time(22, 0), salida=time(6, 0), dias=(1, 2, 3, 4, 5), semanal=Decimal("40.0")
    )

    assert services._horas_por_jornada(horario) == Decimal("8.0")


# ===== SALDO DE LA GESTIÓN =====

def test_asegurar_gestion_devuelve_el_existente_sin_tocarlo():
    """Idempotencia: si el saldo ya existe no se crea ni se incrementa nada."""
    existente = SimpleNamespace(
        id=10, id_empleado=3, gestion=2026, horas_correspondientes=Decimal("160.0")
    )
    db = FakeDb(por_modelo={"Vacacion": existente})

    vacacion, fue_creada = services.asegurar_vacacion_gestion(db, 3, 2026)

    assert vacacion is existente
    assert fue_creada is False
    assert db.agregados == []
    assert db.commits == 0
    assert vacacion.horas_correspondientes == Decimal("160.0")


def test_asegurar_gestion_crea_con_base_lgt():
    """
    Al crear, horas_goce_haber se siembra con la base COMPLETA, no con 0: si no,
    ninguna vacación con goce podría pasar nunca a 'tomado'.
    """
    db = FakeDb(
        por_modelo={"Vacacion": None, "Empleado": _empleado()},
        escalares=[Decimal("160.0")],
    )

    vacacion, fue_creada = services.asegurar_vacacion_gestion(db, 3, 2026)

    assert fue_creada is True
    assert db.commits == 1
    assert len(db.agregados) == 1
    assert vacacion.horas_correspondientes == Decimal("160.0")
    assert vacacion.horas_goce_haber == Decimal("160.0")
    assert vacacion.horas_sin_goce_haber == Decimal("0.0")
    assert vacacion.horas_tomadas == Decimal("0.0")
    assert vacacion.gestion == 2026


def test_asegurar_gestion_sin_base_lgt_usa_cero():
    """Un empleado con menos de un año de antigüedad recibe 0 horas, no None."""
    db = FakeDb(
        por_modelo={"Vacacion": None, "Empleado": _empleado()},
        escalares=[None],
    )

    vacacion, _ = services.asegurar_vacacion_gestion(db, 3, 2026)

    assert vacacion.horas_correspondientes == Decimal("0.0")
    assert vacacion.horas_goce_haber == Decimal("0.0")


def test_asegurar_gestion_empleado_inexistente_es_404():
    db = FakeDb(por_modelo={"Vacacion": None, "Empleado": None})

    with pytest.raises(HTTPException) as exc:
        services.asegurar_vacacion_gestion(db, 999, 2026)

    assert exc.value.status_code == 404
