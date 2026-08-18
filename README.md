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

## Desarrollo

### Frontend

```bash
cd frontend
# Windows PowerShell
Copy-Item .env.example .env.local
pnpm install
pnpm dev
```

Disponible en `http://localhost:3000`.

### Backend

```bash
cd backend
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
Copy-Item .env.example .env
pip install -r requirements.txt
flask --app run.py db upgrade
flask --app run.py run --debug
```

Disponible en `http://localhost:5000`. La comprobación de estado está en `GET /api/health`.

El backend carga las variables de `backend/.env` al ejecutarse mediante el comando `flask`.
Usa `.env.example` como plantilla y no incluyas `.env` en Git. Las variables necesarias son:

- `APP_ENV=development`
- `FRONTEND_ORIGIN=http://localhost:3000`
- `DATABASE_URL` (conexión privada de Neon)
- `SECRET_KEY` (valor aleatorio local)
- `CLOUDINARY_CLOUD_NAME`
- `CLOUDINARY_API_KEY`
- `CLOUDINARY_API_SECRET`

La gestión de fotografías mediante Flask-Admin usa Cloudinary. La consola `/admin/` solo está
habilitada en desarrollo como protección temporal; debe incorporar autenticación administrativa
antes de estar disponible en producción.

## Pendientes de seguridad antes de producción

- Validación del contenido real y límite de tamaño de las imágenes cargadas.
- Reintentos o reconciliación para posibles borrados fallidos en Cloudinary.
