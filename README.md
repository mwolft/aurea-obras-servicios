# AUREA Obras y Servicios

Monorepo sencillo para el frontend en Next.js y la API en Flask.

## Estructura

```text
frontend/  Aplicación Next.js
backend/   API Flask
docs/      Documentación del proyecto
```

## Requisitos

- Node.js 20 o posterior y pnpm.
- Python 3.11 o posterior.
- GNU Make (incluido en GitHub Codespaces y habitualmente disponible en Linux).

## Primera instalación o actualización de dependencias

En un Codespace nuevo, crea primero los archivos de configuración local y completa `backend/.env` con las variables necesarias. No incluyas secretos en Git:

```bash
cp frontend/.env.example frontend/.env.local
cp backend/.env.example backend/.env
```

Después, y siempre que cambien dependencias o falte un paquete, ejecuta desde la raíz:

```bash
make install
```

Este comando crea `backend/.venv` si no existe, instala las dependencias Python de `backend/requirements.txt` dentro de ese entorno virtual e instala las dependencias bloqueadas del frontend con pnpm. No instala paquetes Python globalmente.

En la primera instalación, aplica también las migraciones existentes:

```bash
(cd backend && . .venv/bin/activate && flask --app run.py db upgrade)
```

## Arrancar desarrollo

Una vez hecha la primera instalación, el comando habitual es:

### Todo

```bash
make dev
```

Inicia el frontend y el backend a la vez. Al detenerlo con `Ctrl+C`, el `Makefile` detiene ambos procesos.

### Solo backend

```bash
make backend
```

### Solo frontend

```bash
make frontend
```

- Frontend: `http://localhost:3000`
- Backend/API/Admin: `http://localhost:5000`
- Administración: `http://localhost:5000/admin/`

El backend carga las variables de `backend/.env` al ejecutarse mediante el comando `flask`.
Usa `.env.example` como plantilla y no incluyas `.env` en Git. Las variables necesarias son:

- `APP_ENV=development`
- `FRONTEND_ORIGIN=http://localhost:3000`
- `DATABASE_URL` (conexión privada de Neon)
- `SECRET_KEY` (valor aleatorio local)
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` y `GOOGLE_REDIRECT_URI` (las tres, solo si se activa Google Login; localmente el callback es `http://localhost:5000/api/auth/google/callback`)
- `CLOUDINARY_CLOUD_NAME`
- `CLOUDINARY_API_KEY`
- `CLOUDINARY_API_SECRET`

La autenticación pública usa una cookie de sesión `HttpOnly` emitida por Flask.

## Preparación para producción

El backend está preparado para ejecutarse con Gunicorn en un hosting Linux:

```bash
gunicorn --bind 0.0.0.0:$PORT run:app
```

`run.py` expone la misma `app = create_app()` que se usa en desarrollo; no hay una segunda inicialización para producción. En Windows se mantiene el flujo de desarrollo con `flask`; Gunicorn se ejecutará en el hosting.

Variables obligatorias en producción:

- `APP_ENV=production`
- `DATABASE_URL` de Neon, con SSL requerido según la cadena de conexión proporcionada por Neon.
- `SECRET_KEY`, aleatoria y privada.
- `FRONTEND_ORIGIN=https://<frontend-publico>`.
- `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY` y `CLOUDINARY_API_SECRET`.

Google Login es opcional. Si se activa, deben estar definidas conjuntamente `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` y `GOOGLE_REDIRECT_URI=https://<backend-publico>/api/auth/google/callback`. Registra esa misma URI exacta en Google Cloud. No incluyas secretos ni URLs privadas de Neon en archivos versionados, logs o el frontend.

Proceso de migración recomendado: no ejecutes migraciones automáticamente al iniciar cada instancia web. En cada despliegue compatible, realiza de forma controlada:

```bash
flask --app run.py db upgrade
gunicorn --bind 0.0.0.0:$PORT run:app
```

Primero publica el código, ejecuta `flask db upgrade` como paso de release/manual controlado y después inicia o reinicia las instancias web. `GET /api/health` es público, ligero y no consulta la base de datos, por lo que sirve como healthcheck del proveedor.

Flask-Admin está disponible solo con `APP_ENV=development`. En producción `/admin/` devuelve 404 hasta que exista autenticación y autorización administrativa reales.

### Cookies, CORS y CSRF

En producción la cookie de sesión es `HttpOnly`, `Secure` y `SameSite=Lax`. Con un frontend y una API HTTPS en subdominios del mismo dominio registrable, por ejemplo `www.<dominio>` y `api.<dominio>`, las peticiones son de origen distinto pero del mismo *site*; la cookie puede acompañar a `fetch(..., { credentials: "include" })` y CORS sigue restringido al valor exacto de `FRONTEND_ORIGIN`.

La política actual de `SameSite=Lax` es la protección CSRF proporcional para esa arquitectura same-site. Si el frontend y la API se alojan en sitios distintos, o se requiere `SameSite=None`, hay que implementar protección CSRF explícita antes del despliegue: no basta con cambiar el atributo de la cookie.

No se configura `ProxyFix` por anticipación. El callback de Google usa `GOOGLE_REDIRECT_URI` explícita; si el proveedor exige confiar en cabeceras `X-Forwarded-*`, se deberá configurar con el número de proxies confirmado por ese proveedor.

Para este proyecto pequeño se recomienda **Render** para Flask/Gunicorn: permite variables de entorno, HTTPS y dominio personalizado con una operación sencilla, mientras Neon permanece como PostgreSQL externo. No se añade configuración propietaria hasta elegir y crear el servicio.

### Google Login

Crea en Google Cloud un cliente OAuth 2.0 de tipo **Aplicación web**, configura la pantalla de
consentimiento y añade únicamente los scopes `openid`, `email` y `profile`. Guarda su ID y secreto
en `backend/.env`; nunca en el frontend ni en Git.

Las **Authorized redirect URIs** deben coincidir exactamente con `GOOGLE_REDIRECT_URI`:

- Desarrollo local: `http://localhost:5000/api/auth/google/callback`.
- Codespaces: `https://<url-publica-actual-del-puerto-backend>/api/auth/google/callback`.
- Producción: `https://<backend-publico>/api/auth/google/callback` cuando esa URL esté definida.

En Codespaces, usa la URL HTTPS pública actual del puerto donde se publica Flask tanto en
`NEXT_PUBLIC_API_URL` como en `GOOGLE_REDIRECT_URI`; si el Codespace cambia de URL, actualiza ambas
variables y la URI autorizada en Google Cloud. No hace falta infraestructura adicional.

La gestión de fotografías mediante Flask-Admin usa Cloudinary. La consola `/admin/` solo está
habilitada en desarrollo como protección temporal; debe incorporar autenticación administrativa
antes de estar disponible en producción.

## Pendientes de seguridad antes de producción

- Validación del contenido real y límite de tamaño de las imágenes cargadas.
- Reintentos o reconciliación para posibles borrados fallidos en Cloudinary.
- Protección CSRF explícita si frontend y API dejan de ser same-site en producción.
