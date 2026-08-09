"""
Configuración compartida de pytest.

Importa todos los modelos ANTES de que corra cualquier test, igual que hace
`app/main.py`. SQLAlchemy resuelve las relaciones por nombre de clase contra un
registro global: si un test instancia `Vacacion` sin que `Departamento` esté
importado, el mapper de `Empleado` falla con
`InvalidRequestError: expression 'Departamento' failed to locate a name`.

No crea ninguna base de datos: los tests del repo siguen siendo unitarios, con
`monkeypatch` y dobles (`SimpleNamespace` / `Fake*`).
"""

# --- Employees ---
from app.features.employees.departamento.models import Departamento  # noqa: F401
from app.features.employees.complementodepartamento.models import ComplementoDep  # noqa: F401
from app.features.employees.cargo.models import Cargo  # noqa: F401
from app.features.employees.empleado.models import Empleado  # noqa: F401
from app.features.employees.horario.models import Horario, AsignacionHorario  # noqa: F401
from app.features.employees.horario_personalizado.models import HorarioPersonalizadoEmpleado  # noqa: F401

# --- Auth ---
from app.features.auth.rol.models import Rol  # noqa: F401
from app.features.auth.usuario.models import Usuario  # noqa: F401

# --- Contracts ---
from app.features.contracts.contrato.models import Contrato  # noqa: F401
from app.features.contracts.ajuste_salarial.models import (  # noqa: F401
    AjusteSalarial, DecretoIncrementoSalarial, CondicionDecreto, ParametroImpuesto
)

# --- Attendance ---
from app.features.attendance.marcacion.models import (  # noqa: F401
    Marcacion, ArchivoExcel, IncidenciaMarcacion
)
from app.features.attendance.asistencia_diaria.models import (  # noqa: F401
    AsistenciaDiaria, PeriodoAsistencia
)
from app.features.attendance.feriados.models import DiaFestivo  # noqa: F401
from app.features.attendance.beneficio_cumpleanos.models import BeneficioCumpleanos  # noqa: F401
from app.features.attendance.justificacion.models import JustificacionAusencia  # noqa: F401
from app.features.attendance.vacaciones.models import Vacacion, DetalleVacacion  # noqa: F401
from app.features.attendance.compensacion_horas_extra.models import CompensacionHorasExtra  # noqa: F401

# --- Reports ---
from app.features.reports.reporte.models import Reporte  # noqa: F401
