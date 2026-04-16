# SEMANA 2 - Módulo Auth (Rol + Usuario)

**Fecha de completación:** 2026-03-24  
**Objetivo:** Sistema de autenticación completo con roles y usuarios (sin JWT hasta Semana 9)

---

## 📦 Lo que se construyó

### 1. Modelo Usuario
- **Ubicación:** `app/features/auth/usuario/models.py`
- **Características:**
  - Tabla `usuario` con campos: id, username, password_hash, id_rol, id_empleado, email, activo, ultimo_acceso
  - Contraseñas hasheadas con bcrypt (passlib)
  - Relación N:1 con Rol
  - Relación 1:1 opcional con Empleado
  - Métodos de utilidad: hash_password(), verify_password(), set_password(), check_password()

### 2. Actualización modelo Rol
- Activación de relación `usuarios` con Usuario

### 3. Schemas Pydantic
- **Rol:** RolCreate, RolUpdate, RolRead, RolReadSimple
- **Usuario:** UsuarioCreate, UsuarioUpdate, UsuarioRead, UsuarioReadWithRol, UsuarioReadSimple, UsuarioChangePassword
- **Seguridad:** El campo password_hash NUNCA se expone en responses

### 4. Services (Lógica de negocio)
#### Rol: CRUD completo + validaciones
#### Usuario: CRUD completo + hash de contraseñas + verify_credentials

### 5. Routers (Endpoints REST)
#### Rol: 7 endpoints documentados
#### Usuario: 9 endpoints documentados

### 6. Script de seed actualizado
- Crea usuario admin inicial (username: admin, password: admin123)

---

## 📝 Comandos para ejecutar MANUALMENTE

### 1. Generar migración
```bash
alembic revision --autogenerate -m "semana2_auth_usuario"
```

### 2. Aplicar migración
```bash
alembic upgrade head
```

### 3. Ejecutar seed
```bash
python scripts/seed_inicial.py
```

### 4. Ejecutar aplicación
```bash
uvicorn app.main:app --reload --port 8000
```

### 5. Ver documentación
http://localhost:8000/docs

---

## 🔑 Decisiones técnicas

1. **Hash con bcrypt** - password_hash nunca se expone
2. **JWT NO activado** hasta Semana 9 - endpoints abiertos
3. **Usuario-Empleado 1:1 opcional** - permite usuarios externos
4. **Soft delete** implementado con campo activo
5. **Validaciones completas** - username único, rol con usuarios no se puede eliminar

---

## 🔄 Próxima semana: SEMANA 3 - Módulo Employees

- CRUD Departamento, Cargo, Empleado
- Modelos Horario y AsignacionHorario
- Búsqueda por CI
- Migración 3

---

## ✅ Archivos creados/modificados

### Creados:
- app/features/auth/usuario/models.py
- app/features/auth/rol/schemas.py
- app/features/auth/usuario/schemas.py
- app/features/auth/rol/services.py
- app/features/auth/usuario/services.py
- app/features/auth/rol/router.py
- app/features/auth/usuario/router.py

### Actualizados:
- app/features/auth/rol/models.py
- app/features/employees/empleado/models.py
- app/features/employees/cargo/models.py
- app/features/employees/departamento/models.py
- app/main.py
- alembic/env.py
- requirements.txt
- scripts/seed_inicial.py

---

**Stack:** FastAPI + SQLAlchemy 2.0 + PostgreSQL + Pydantic v2  
**Arquitecto:** Claude Sonnet 4.5
