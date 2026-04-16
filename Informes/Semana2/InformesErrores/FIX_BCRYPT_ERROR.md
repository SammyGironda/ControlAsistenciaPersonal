# 🔧 SOLUCIÓN: Error de Compatibilidad bcrypt + passlib

## ❌ Error Detectado

```
ValueError: password cannot be longer than 72 bytes
AttributeError: module 'bcrypt' has no attribute '__about__'
```

## ✅ Causa

La versión de `bcrypt` instalada es demasiado moderna para `passlib==1.7.4`, causando:
1. Incompatibilidad de API (falta atributo `__about__`)
2. Violación del límite de 72 bytes de bcrypt sin manejo adecuado

## ✅ Solución Implementada

### 1. **Actualización de `requirements.txt`**
   - Se fijó `bcrypt==4.0.1` (compatible con passlib 1.7.4)
   - Anteriormente: `passlib[bcrypt]==1.7.4` (instalaba última bcrypt)
   - Ahora: `passlib==1.7.4` + `bcrypt==4.0.1` (versiones compatibles)

### 2. **Modificación de `models.py`**
   - Se agregó truncamiento automático a 72 bytes en:
     - `hash_password()`: Trunca antes de hashear
     - `verify_password()`: Trunca antes de verificar
   - **Seguridad**: Previene errores y es buena práctica

## 📋 PASOS PARA APLICAR LA SOLUCIÓN

### **PASO 1: Reinstalar dependencias**

```powershell
# 1. Activar entorno virtual
cd d:\DOCUMENTOS\Desktop\BLUENET\02PROYECTO\v13
.\venv\Scripts\activate

# 2. Desinstalar versión problemática
pip uninstall bcrypt -y

# 3. Instalar versión compatible
pip install bcrypt==4.0.1

# 4. Verificar instalación
pip list | findstr bcrypt
# Debe mostrar: bcrypt 4.0.1
```

### **PASO 2: Reiniciar el servidor FastAPI**

```powershell
# Si el servidor está corriendo, detenerlo (Ctrl+C)
# Luego reiniciarlo:
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### **PASO 3: Probar endpoint de creación de usuario**

```bash
# Usar Postman o curl
POST http://localhost:8000/api/v1/usuarios/
Content-Type: application/json

{
  "username": "juan.perez",
  "password": "Password123!",
  "id_rol": 2,
  "id_empleado": 1,
  "activo": true
}
```

## ✅ Verificación Final

1. ✅ `pip list | findstr bcrypt` → `bcrypt 4.0.1`
2. ✅ `pip list | findstr passlib` → `passlib 1.7.4`
3. ✅ Servidor inicia sin errores
4. ✅ Endpoint POST `/api/v1/usuarios/` funciona correctamente

## 📝 Cambios en el Código

### `requirements.txt`
```diff
- passlib[bcrypt]==1.7.4
+ passlib==1.7.4
+ bcrypt==4.0.1
```

### `app/features/auth/usuario/models.py`
```python
@staticmethod
def hash_password(password: str) -> str:
    # Truncar a 72 bytes para cumplir con límite de bcrypt
    password_bytes = password.encode('utf-8')[:72]
    return pwd_context.hash(password_bytes)

@staticmethod
def verify_password(plain_password: str, hashed_password: str) -> bool:
    # Truncar a 72 bytes igual que en hash_password
    password_bytes = plain_password.encode('utf-8')[:72]
    return pwd_context.verify(password_bytes, hashed_password)
```

## 🎯 Notas Importantes

1. **El límite de 72 bytes de bcrypt es estándar** - no es un bug
2. **El truncamiento es seguro** - 72 caracteres ASCII = contraseña muy fuerte
3. **Versiones fijadas** - previene futuros conflictos de dependencias
4. **Semana 9** - Cuando activemos JWT, verificar compatibilidad con `python-jose`

---

**Creado**: 2026-03-31  
**Estado**: ✅ Resuelto
