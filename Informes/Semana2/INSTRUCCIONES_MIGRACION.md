# INSTRUCCIONES: Ejecutar Migración de Semana 2

## 🎯 Objetivo
Crear la tabla \ en la base de datos con la migración de Alembic.

## 📋 Pasos a seguir

### PASO 1: Generar la migración

Abre tu terminal (cmd, PowerShell o Git Bash) y ejecuta:

**Si el comando \ no se encuentra**, prueba alguna de estas alternativas:

#### Opción A: Con Python directamente
#### Opción B: Activar entorno virtual (si usas uno)
#### Opción C: Ruta completa de alembic
### PASO 2: Verificar la migración generada

Deberías ver un nuevo archivo en:
Ábrelo y verifica que contenga:
- \ con todas las columnas
- Foreign keys a \ y 
### PASO 3: Aplicar la migración

Deberías ver:
### PASO 4: Verificar en PostgreSQL

Abre psql o pgAdmin y ejecuta:

### PASO 5: Ejecutar script de seed

Deberías ver:
### PASO 6: Iniciar la aplicación

### PASO 7: Probar en Swagger

Abre: http://localhost:8000/docs

Prueba estos endpoints:
1. **GET /api/v1/roles** - Debería listar 5 roles
2. **GET /api/v1/usuarios** - Debería listar el usuario admin
3. **POST /api/v1/usuarios/verify-credentials**
   - username: admin
   - password: admin123
   - Debería retornar: 
## ❌ Troubleshooting

### Error: "alembic: command not found"
- Verifica instalación: - Reinstala: - Usa ruta completa o activa entorno virtual

### Error: "can't connect to database"
- Verifica que PostgreSQL esté corriendo
- Revisa DATABASE_URL en .env
- Conecta manualmente: 
### Error: "No module named 'app'"
- Asegúrate de estar en el directorio raíz del proyecto
- Verifica PYTHONPATH o ejecuta desde la raíz

### La migración no detecta cambios
- Verifica que \ exista
- Verifica que esté importado en \ (línea 19)
- Usa \ en el comando

### El seed falla con "rol no encontrado"
- Primero aplica la migración: - Luego ejecuta el seed: 
## ✅ Confirmación de éxito

Si todo funcionó correctamente:
- ✅ Tabla \ existe en PostgreSQL
- ✅ Usuario admin creado
- ✅ Swagger muestra endpoints de /roles y /usuarios
- ✅ Puedes verificar credenciales del admin

---

**¿Listo para continuar?**
Una vez completados estos pasos, estarás listo para la **Semana 3: Módulo Employees**\!
