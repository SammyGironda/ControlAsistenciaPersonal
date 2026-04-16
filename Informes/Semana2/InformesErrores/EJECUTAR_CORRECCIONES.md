# 🚀 INSTRUCCIONES DE EJECUCIÓN - Corrección bcrypt

## ⚡ OPCIÓN 1: Ejecutar Script Automático (RECOMENDADO)

### **Windows CMD / PowerShell:**

```cmd
cd d:\DOCUMENTOS\Desktop\BLUENET\02PROYECTO\v13
fix_bcrypt.bat
```

O con PowerShell:

```powershell
cd d:\DOCUMENTOS\Desktop\BLUENET\02PROYECTO\v13
.\fix_bcrypt.ps1
```

---

## 🔧 OPCIÓN 2: Ejecución Manual Paso a Paso

### **PASO 1: Abrir terminal**
- Presiona `Windows + R`
- Escribe `cmd` y presiona Enter
- O busca "CMD" en el menú inicio

### **PASO 2: Ir al directorio del proyecto**
```cmd
cd d:\DOCUMENTOS\Desktop\BLUENET\02PROYECTO\v13
```

### **PASO 3: Activar entorno virtual**
```cmd
venv\Scripts\activate.bat
```

Tu prompt debería cambiar a algo como:
```
(venv) d:\DOCUMENTOS\Desktop\BLUENET\02PROYECTO\v13>
```

### **PASO 4: Desinstalar bcrypt incompatible**
```cmd
python -m pip uninstall bcrypt -y
```

**Salida esperada:**
```
Successfully uninstalled bcrypt-X.X.X
```

### **PASO 5: Instalar bcrypt 4.0.1**
```cmd
python -m pip install bcrypt==4.0.1
```

**Salida esperada:**
```
Successfully installed bcrypt-4.0.1
```

### **PASO 6: Verificar versión instalada**
```cmd
python -m pip list | findstr bcrypt
```

**Salida esperada:**
```
bcrypt        4.0.1
```

### **PASO 7: Generar migración**
```cmd
alembic revision --autogenerate -m "semana2_fix_quitar_email_usuario"
```

**Salida esperada:**
```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.autogenerate.compare] Detected removed column 'usuario.email'
Generating d:\...\alembic\versions\XXXXX_semana2_fix_quitar_email_usuario.py ...  done
```

### **PASO 8: Revisar migración generada** ⚠️ IMPORTANTE
```cmd
notepad alembic\versions\XXXXX_semana2_fix_quitar_email_usuario.py
```

**Verificar que contenga:**
```python
def upgrade() -> None:
    op.drop_column('usuario', 'email', schema='rrhh')

def downgrade() -> None:
    op.add_column('usuario', sa.Column('email', ...))
```

### **PASO 9: Aplicar migración**
```cmd
alembic upgrade head
```

**Salida esperada:**
```
INFO  [alembic.runtime.migration] Running upgrade XXXXX -> YYYYY, semana2_fix_quitar_email_usuario
```

### **PASO 10: Verificar estado de alembic**
```cmd
alembic current
```

**Salida esperada:**
```
YYYYY (head)
```

### **PASO 11: Iniciar servidor**
```cmd
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Salida esperada:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

---

## ✅ VERIFICACIÓN FINAL

### **1. Probar creación de usuario**

Abre Postman o tu navegador en: http://localhost:8000/docs

Ejecuta:
```
POST /api/v1/usuarios/
```

Con body:
```json
{
  "username": "test.user",
  "password": "Test123!",
  "id_rol": 1,
  "activo": true
}
```

**Esperado**: HTTP 200 + usuario creado SIN campo `email`

### **2. Verificar que NO haya campo email**

```
GET /api/v1/usuarios/
```

**Esperado**: Lista de usuarios donde NINGUNO tiene campo `email`

---

## ❌ SOLUCIÓN DE PROBLEMAS

### **Error: "bcrypt is not installed"**
```cmd
python -m pip install bcrypt==4.0.1
```

### **Error: "alembic: command not found"**
```cmd
python -m pip install alembic
```

### **Error: "No changes detected"**
Verifica que hayas guardado los cambios en `models.py`. El campo `email` debe estar eliminado.

### **Error al conectar a PostgreSQL**
Verifica tu archivo `.env`:
```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=tu_password
POSTGRES_DB=rrhh_bolivia_db
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

---

## 📞 ¿NECESITAS AYUDA?

Si algo falla:

1. **Captura el error completo** (texto del error)
2. **Copia el comando que ejecutaste**
3. **Verifica que estés en el directorio correcto**
4. **Asegúrate que el entorno virtual esté activado**

---

**Creado**: 2026-03-31  
**Última actualización**: 2026-03-31
