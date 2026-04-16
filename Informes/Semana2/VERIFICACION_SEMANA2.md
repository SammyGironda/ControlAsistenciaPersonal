# 📋 VERIFICACIÓN SEMANA 2 - Módulo Auth (Rol + Usuario)

**Fecha**: 2026-03-31  
**Estado**: ⚠️ Correcciones Aplicadas

---

## 🔍 PROBLEMAS DETECTADOS Y RESUELTOS

### 1. ❌ Campo `email` Duplicado
**Problema**: El campo `email` estaba en **Usuario** y **Empleado**

**Análisis**:
- Según `codigoPostgresSQL.txt` (fuente de verdad), `email` solo debe estar en `empleado`
- `email` es un dato **personal del empleado**, no del sistema de autenticación
- Un usuario puede existir sin empleado (admin externo), pero ese usuario NO necesita email

**Solución**:
✅ Eliminado campo `email` de:
- `app/features/auth/usuario/models.py`
- `app/features/auth/usuario/schemas.py` (todos los schemas)
- `app/features/auth/usuario/services.py`
- `app/features/auth/usuario/router.py` (docstring)

**Próximo paso**: Generar migración para quitar columna de BD

---

### 2. ❌ Error de Compatibilidad bcrypt
**Problema**: `ValueError: password cannot be longer than 72 bytes`

**Causa raíz**:
- `passlib[bcrypt]==1.7.4` instalaba última versión de bcrypt (>4.1)
- Incompatibilidad de API entre passlib 1.7.4 y bcrypt moderno
- Falta manejo del límite de 72 bytes de bcrypt

**Solución**:
✅ Actualizado `requirements.txt`:
```diff
- passlib[bcrypt]==1.7.4
+ passlib==1.7.4
+ bcrypt==4.0.1
```

✅ Modificado `models.py` para truncar contraseñas:
```python
@staticmethod
def hash_password(password: str) -> str:
    password_bytes = password.encode('utf-8')[:72]
    return pwd_context.hash(password_bytes)
```

**Comando para aplicar**:
```powershell
pip uninstall bcrypt -y
pip install bcrypt==4.0.1
```

---

## 📂 ARCHIVOS MODIFICADOS

| Archivo | Cambio |
|---------|--------|
| `requirements.txt` | Fijada versión `bcrypt==4.0.1` |
| `app/features/auth/usuario/models.py` | ✅ Eliminado `email` + truncamiento 72 bytes |
| `app/features/auth/usuario/schemas.py` | ✅ Eliminado `email` de todos los schemas |
| `app/features/auth/usuario/services.py` | ✅ Eliminado `email` de respuestas |
| `app/features/auth/usuario/router.py` | ✅ Eliminado `email` del docstring |

---

## 🔧 COMANDOS PENDIENTES DE EJECUCIÓN

### **1. Reinstalar dependencias** ⚠️ EJECUTAR PRIMERO
```powershell
cd d:\DOCUMENTOS\Desktop\BLUENET\02PROYECTO\v13
.\venv\Scripts\activate
pip uninstall bcrypt -y
pip install bcrypt==4.0.1
pip list | findstr bcrypt  # Verificar: debe mostrar 4.0.1
```

### **2. Generar migración para quitar email** ⚠️ EJECUTAR DESPUÉS
```powershell
alembic revision --autogenerate -m "semana2_fix_quitar_email_usuario"
# Revisar archivo generado en alembic/versions/
# Debe contener: op.drop_column('usuario', 'email', schema='rrhh')
```

### **3. Aplicar migración**
```powershell
alembic upgrade head
```

### **4. Reiniciar servidor**
```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## ✅ VERIFICACIÓN DE FUNCIONALIDAD

### **Test 1: Crear Usuario**
```json
POST http://localhost:8000/api/v1/usuarios/
{
  "username": "admin.sistema",
  "password": "Admin123!",
  "id_rol": 1,
  "id_empleado": null,
  "activo": true
}
```
**Esperado**: HTTP 200 + usuario creado sin `email` en respuesta

### **Test 2: Crear Usuario Vinculado a Empleado**
```json
POST http://localhost:8000/api/v1/usuarios/
{
  "username": "juan.perez",
  "password": "Password123!",
  "id_rol": 4,
  "id_empleado": 1,
  "activo": true
}
```
**Esperado**: HTTP 200 + usuario vinculado

### **Test 3: Listar Usuarios**
```
GET http://localhost:8000/api/v1/usuarios/
```
**Esperado**: Lista de usuarios SIN campo `email`

### **Test 4: Login (verificar hash)**
```json
POST http://localhost:8000/api/v1/usuarios/login
{
  "username": "admin.sistema",
  "password": "Admin123!"
}
```
**Esperado**: HTTP 200 + usuario autenticado

---

## 📊 ESTADO DE LA SEMANA 2

| Componente | Estado | Notas |
|------------|--------|-------|
| Modelo `Rol` | ✅ OK | Sin cambios |
| Modelo `Usuario` | ✅ CORREGIDO | Email eliminado + bcrypt fix |
| Schemas Pydantic | ✅ CORREGIDO | Email eliminado |
| Services CRUD | ✅ CORREGIDO | Email eliminado |
| Router Endpoints | ✅ CORREGIDO | Docstring actualizado |
| Migración Alembic | ⚠️ PENDIENTE | Generar con --autogenerate |
| Hash Contraseñas | ✅ CORREGIDO | Truncamiento 72 bytes |
| Tests | ⚠️ PENDIENTE | Crear en Semana 9 |

---

## 📝 DECISIONES TÉCNICAS

### **1. ¿Por qué quitar email de Usuario?**
- **Arquitectura limpia**: Email es dato personal del empleado
- **Fuente de verdad**: `codigoPostgresSQL.txt` solo tiene email en empleado
- **Flexibilidad**: Un admin externo puede no tener empleado NI email
- **Contacto**: Si el usuario está vinculado a empleado, usar `usuario.empleado.email`

### **2. ¿Por qué bcrypt 4.0.1 y no la última?**
- **Compatibilidad**: passlib 1.7.4 (última estable) funciona con bcrypt 4.0.x
- **Estabilidad**: Evita problemas de API entre bibliotecas
- **Producción**: Versiones fijadas previenen sorpresas en deploys

### **3. ¿Es seguro truncar a 72 bytes?**
- **SÍ**: 72 caracteres ASCII = contraseña extremadamente fuerte
- **Estándar**: bcrypt siempre ha tenido este límite
- **Buena práctica**: Manejar explícitamente en lugar de fallar silenciosamente

---

## 🎯 PRÓXIMOS PASOS

1. ✅ **Ejecutar comandos pendientes** (arriba)
2. ✅ **Verificar tests** (crear usuarios, login)
3. ✅ **Probar Swagger UI** (http://localhost:8000/docs)
4. 🔜 **Semana 3**: Módulo Employees completo

---

## 📚 DOCUMENTACIÓN ADICIONAL

Ver archivo raíz del proyecto:
- `FIX_BCRYPT_ERROR.md` - Solución detallada del error bcrypt

---

**Conclusión**: Semana 2 requiere ejecutar comandos pendientes para completarse. Una vez aplicadas las correcciones, el módulo Auth estará 100% funcional según especificaciones.
