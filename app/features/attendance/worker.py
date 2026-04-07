"""
Worker de procesamiento automático de asistencia diaria.
Ejecuta diariamente a las 23:59 para calcular la asistencia del día.

Configuración:
- APScheduler con CronTrigger
- Ejecuta a las 23:59 todos los días
- Procesa el día actual (que está por terminar)
- Logs de ejecución para monitoreo
"""

import logging
from datetime import date, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.features.attendance.asistencia_diaria.services import procesar_asistencia_masiva

# Configurar logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Instancia global del scheduler
scheduler: BackgroundScheduler = None


def job_calcular_asistencia_diaria():
    """
    Job que se ejecuta diariamente a las 23:59.
    Calcula la asistencia de todos los empleados para el día actual.
    
    Nota: Procesa el día actual porque se ejecuta a las 23:59,
    cuando el día laboral ya terminó y todas las marcaciones están registradas.
    """
    fecha_a_procesar = date.today()
    
    logger.info(f"[WORKER] Iniciando cálculo de asistencia para {fecha_a_procesar}")
    
    # Crear sesión de base de datos
    db: Session = SessionLocal()
    
    try:
        # Procesar asistencia masiva
        resultado = procesar_asistencia_masiva(db, fecha_a_procesar)
        
        # Log de resultados
        logger.info(
            f"[WORKER] Procesamiento completado para {fecha_a_procesar}:\n"
            f"  - Empleados procesados: {resultado.empleados_procesados}\n"
            f"  - Empleados con error: {resultado.empleados_con_error}\n"
            f"  - Empleados skipped: {resultado.empleados_skipped}"
        )
        
        if resultado.errores:
            logger.warning(f"[WORKER] Errores encontrados:\n" + "\n".join(resultado.errores[:10]))
        
    except Exception as e:
        logger.error(f"[WORKER] Error crítico al procesar asistencia: {str(e)}", exc_info=True)
    finally:
        db.close()
        logger.info("[WORKER] Job de asistencia diaria finalizado")


def start_scheduler():
    """
    Inicia el scheduler de APScheduler.
    Debe llamarse al iniciar la aplicación (en main.py startup event).
    
    Configuración:
    - BackgroundScheduler: Ejecuta en segundo plano sin bloquear la app
    - CronTrigger: Ejecuta a las 23:59 todos los días
    - timezone: 'America/La_Paz' (hora de Bolivia: UTC-4)
    """
    global scheduler
    
    if scheduler is not None:
        logger.warning("[WORKER] Scheduler ya está iniciado. Ignorando llamada duplicada.")
        return
    
    logger.info("[WORKER] Inicializando scheduler de asistencia diaria...")
    
    # Crear scheduler
    scheduler = BackgroundScheduler(timezone="America/La_Paz")
    
    # Agregar job con CronTrigger (23:59 todos los días)
    scheduler.add_job(
        func=job_calcular_asistencia_diaria,
        trigger=CronTrigger(hour=23, minute=59),
        id="calcular_asistencia_diaria",
        name="Calcular asistencia diaria de empleados",
        replace_existing=True,
        max_instances=1  # Solo una instancia del job a la vez
    )
    
    # Iniciar scheduler
    scheduler.start()
    
    logger.info("[WORKER] Scheduler iniciado exitosamente. Job programado para las 23:59 diarias.")
    logger.info(f"[WORKER] Próxima ejecución: {scheduler.get_job('calcular_asistencia_diaria').next_run_time}")


def shutdown_scheduler():
    """
    Detiene el scheduler de forma segura.
    Debe llamarse al apagar la aplicación (en main.py shutdown event).
    """
    global scheduler
    
    if scheduler is None:
        logger.warning("[WORKER] Scheduler no estaba iniciado.")
        return
    
    logger.info("[WORKER] Deteniendo scheduler...")
    
    # Detener scheduler (wait=True espera a que termine el job actual si está corriendo)
    scheduler.shutdown(wait=True)
    scheduler = None
    
    logger.info("[WORKER] Scheduler detenido correctamente.")


def ejecutar_job_manualmente(fecha: date = None):
    """
    Ejecuta el job manualmente para una fecha específica.
    Útil para pruebas o reprocesar días pasados.
    
    Args:
        fecha: Fecha a procesar. Si es None, procesa hoy.
    
    Usage:
        >>> from app.features.attendance.worker import ejecutar_job_manualmente
        >>> from datetime import date
        >>> ejecutar_job_manualmente(date(2026, 1, 15))
    """
    if fecha is None:
        fecha = date.today()
    
    logger.info(f"[WORKER MANUAL] Ejecutando cálculo manual para {fecha}")
    
    db: Session = SessionLocal()
    
    try:
        resultado = procesar_asistencia_masiva(db, fecha)
        
        logger.info(
            f"[WORKER MANUAL] Procesamiento manual completado:\n"
            f"  - Fecha: {fecha}\n"
            f"  - Procesados: {resultado.empleados_procesados}\n"
            f"  - Errores: {resultado.empleados_con_error}\n"
            f"  - Skipped: {resultado.empleados_skipped}"
        )
        
        return resultado
        
    except Exception as e:
        logger.error(f"[WORKER MANUAL] Error: {str(e)}", exc_info=True)
        raise
    finally:
        db.close()


# ============================================================
# FUNCIONES DE TESTING
# ============================================================

def get_scheduler_status() -> dict:
    """
    Retorna el estado actual del scheduler para monitoreo.
    
    Returns:
        dict con información del scheduler y jobs programados
    """
    if scheduler is None:
        return {
            "running": False,
            "message": "Scheduler no iniciado"
        }
    
    jobs = scheduler.get_jobs()
    
    return {
        "running": scheduler.running,
        "jobs_count": len(jobs),
        "jobs": [
            {
                "id": job.id,
                "name": job.name,
                "next_run_time": str(job.next_run_time),
                "trigger": str(job.trigger)
            }
            for job in jobs
        ]
    }


def test_job_ahora():
    """
    Ejecuta el job AHORA para testing (sin esperar a las 23:59).
    Solo para desarrollo y pruebas.
    
    ⚠️ NO usar en producción ⚠️
    """
    logger.warning("[WORKER TEST] Ejecutando job de prueba AHORA (testing only)")
    job_calcular_asistencia_diaria()
