"""
Modelos para Marcaciones, Archivos Excel e Incidencias.
Sistema de registro biométrico y gestión de importaciones Excel.
"""

from datetime import datetime
from typing import Optional, TYPE_CHECKING, List
from sqlalchemy import String, Integer, BigInteger, ForeignKey, Boolean, Text, Enum as SQLEnum, TIMESTAMP, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.db.base import Base

if TYPE_CHECKING:
    from app.features.employees.empleado.models import Empleado
    from app.features.auth.usuario.models import Usuario


# --- ENUMs ---
class OrigenDatoEnum(str, enum.Enum):
    """
    Origen del registro de marcación.
    Permite transición Fase 1 (Excel) → Fase 2 (Biométrico en tiempo real).
    """
    Excel = "Excel"
    API_Biometrico = "API_Biometrico"
    Manual = "Manual"


class TipoMarcacionEnum(str, enum.Enum):
    """Tipo de marcación biométrica."""
    ENTRADA = "ENTRADA"
    SALIDA = "SALIDA"


class EstadoProcesamientoEnum(str, enum.Enum):
    """Estado del procesamiento de un archivo Excel."""
    pendiente = "pendiente"
    procesando = "procesando"
    completado = "completado"
    error = "error"


class TipoIncidenciaEnum(str, enum.Enum):
    """Tipo de incidencia en marcación."""
    huerfana = "huerfana"
    duplicada = "duplicada"
    inconsistente = "inconsistente"


class EstadoResolucionEnum(str, enum.Enum):
    """Estado de resolución de una incidencia."""
    pendiente = "pendiente"
    resuelto = "resuelto"
    ignorado = "ignorado"


# ============================================================
# 1. ARCHIVO EXCEL
# ============================================================

class ArchivoExcel(Base):
    """
    Tabla: rrhh.archivo_excel
    Log de importaciones de archivos Excel con marcaciones.

    Lógica de negocio:
    - Se crea un registro al subir el archivo
    - estado_procesamiento rastrea el progreso async
    - log_errores almacena JSON con filas problemáticas
    - SET NULL en id_subido_por: preservar log aunque se elimine usuario
    """

    __tablename__ = "archivo_excel"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nombre_archivo: Mapped[str] = mapped_column(String(255), nullable=False)
    ruta_storage: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Ruta física del archivo en el servidor"
    )
    id_subido_por: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("usuario.id", ondelete="SET NULL"),
        nullable=True,
        comment="SET NULL: preservar log aunque el usuario sea eliminado"
    )
    fecha_subida: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        default=datetime.now,
        nullable=False
    )
    estado_procesamiento: Mapped[EstadoProcesamientoEnum] = mapped_column(
        SQLEnum(EstadoProcesamientoEnum, name="estado_procesamiento_enum", create_constraint=True, native_enum=False),
        default=EstadoProcesamientoEnum.pendiente,
        nullable=False
    )
    total_filas: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    filas_procesadas: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    filas_con_error: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    log_errores: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="JSON con detalle de filas problemáticas"
    )

    # --- Auditoría ---
    created_at: Mapped[datetime] = mapped_column(default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now, onupdate=datetime.now, nullable=False
    )

    # --- Relaciones ---
    subido_por: Mapped[Optional["Usuario"]] = relationship("Usuario")
    marcaciones: Mapped[List["Marcacion"]] = relationship(
        "Marcacion",
        back_populates="archivo",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ArchivoExcel(id={self.id}, nombre='{self.nombre_archivo}', estado='{self.estado_procesamiento}')>"


# ============================================================
# 2. MARCACION
# ============================================================


class Marcacion(Base):
    """
    Tabla: rrhh.marcacion
    Registro biométrico central del sistema.

    Lógica de negocio:
    - origen_dato permite convivir Excel y API sin cambiar lógica de cálculo
    - id_marcacion_par vincula ENTRADA con SALIDA para formar jornada completa
    - es_duplicada: detecta dos marcaciones consecutivas del mismo tipo
    - es_huerfana: entrada sin salida o viceversa (genera incidencia)
    - SET NULL en id_marcacion_par: si se elimina una, la otra queda huérfana
    """

    __tablename__ = "marcacion"

    # --- Columnas principales ---
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    id_empleado: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("empleado.id", ondelete="CASCADE"),
        nullable=False
    )
    fecha_hora_marcacion: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        comment="Timestamp exacto de la marcación"
    )
    tipo_marcacion: Mapped[TipoMarcacionEnum] = mapped_column(
        SQLEnum(TipoMarcacionEnum, name="tipo_marcacion_enum", create_constraint=True, native_enum=False),
        nullable=False
    )
    origen_dato: Mapped[OrigenDatoEnum] = mapped_column(
        SQLEnum(OrigenDatoEnum, name="origen_dato_enum", create_constraint=True, native_enum=False),
        default=OrigenDatoEnum.Excel,
        nullable=False,
        comment="Clave de transición Fase1→Fase2"
    )

    # --- Relación con archivo Excel (opcional) ---
    id_archivo_excel: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("archivo_excel.id", ondelete="SET NULL"),
        nullable=True,
        comment="NULL si origen no es Excel"
    )

    # --- Emparejamiento de marcaciones ---
    id_marcacion_par: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("marcacion.id", ondelete="SET NULL"),
        nullable=True,
        comment="FK autorreferencial: ENTRADA↔SALIDA. SET NULL: si se elimina una, la otra queda huérfana"
    )

    # --- Flags de validación ---
    es_duplicada: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="TRUE = dos marcaciones del mismo tipo consecutivas"
    )
    es_huerfana: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="TRUE = no tiene pareja (entrada sin salida o viceversa)"
    )

    # --- Observaciones ---
    observacion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # --- Auditoría ---
    created_at: Mapped[datetime] = mapped_column(default=datetime.now, nullable=False)

    # --- Índices ---
    __table_args__ = (
        Index('idx_marcacion_empleado_fecha', 'id_empleado', 'fecha_hora_marcacion'),
    )

    # --- Relaciones ---
    empleado: Mapped["Empleado"] = relationship(
        "Empleado",
        back_populates="marcaciones"
    )
    archivo: Mapped[Optional["ArchivoExcel"]] = relationship(
        "ArchivoExcel",
        back_populates="marcaciones"
    )
    marcacion_par: Mapped[Optional["Marcacion"]] = relationship(
        "Marcacion",
        remote_side=[id],
        foreign_keys=[id_marcacion_par]
    )
    incidencia: Mapped[Optional["IncidenciaMarcacion"]] = relationship(
        "IncidenciaMarcacion",
        back_populates="marcacion",
        uselist=False
    )

    def __repr__(self) -> str:
        return f"<Marcacion(id={self.id}, empleado_id={self.id_empleado}, tipo='{self.tipo_marcacion}', fecha={self.fecha_hora_marcacion})>"


# ============================================================
# 3. INCIDENCIA MARCACION
# ============================================================

class IncidenciaMarcacion(Base):
    """
    Tabla: rrhh.incidencia_marcacion
    Respaldo de marcaciones problemáticas.

    Lógica de negocio:
    - Se crea automáticamente por trigger cuando es_huerfana o es_duplicada
    - evidencia_url apunta a documento que respalda resolución
    - SET NULL en id_resuelto_por: preservar historial aunque se elimine usuario
    - UNIQUE en id_marcacion: una marcación solo puede tener una incidencia
    """

    __tablename__ = "incidencia_marcacion"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_marcacion: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("marcacion.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )
    tipo_incidencia: Mapped[TipoIncidenciaEnum] = mapped_column(
        SQLEnum(
            TipoIncidenciaEnum,
            name="tipo_incidencia_enum",
            create_constraint=True,
            native_enum=False,
            length=19,
        ),
        nullable=False
    )
    estado_resolucion: Mapped[EstadoResolucionEnum] = mapped_column(
        SQLEnum(
            EstadoResolucionEnum,
            name="estado_resolucion_enum",
            create_constraint=True,
            native_enum=False,
            length=10,
        ),
        default=EstadoResolucionEnum.pendiente,
        nullable=False
    )
    evidencia_url: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="URL de documento escaneado o correo que respalda la resolución"
    )
    descripcion_resolucion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    id_resuelto_por: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("empleado.id", ondelete="SET NULL"),
        nullable=True,
        comment="SET NULL: preservar historial aunque el usuario sea eliminado"
    )
    fecha_resolucion: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, nullable=True)

    # --- Auditoría ---
    created_at: Mapped[datetime] = mapped_column(default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now, onupdate=datetime.now, nullable=False
    )

    # --- Relaciones ---
    marcacion: Mapped["Marcacion"] = relationship(
        "Marcacion",
        back_populates="incidencia"
    )
    resuelto_por: Mapped[Optional["Empleado"]] = relationship(
        "Empleado",
        foreign_keys=[id_resuelto_por],
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<IncidenciaMarcacion(id={self.id}, marcacion_id={self.id_marcacion}, tipo='{self.tipo_incidencia}', estado='{self.estado_resolucion}')>"

