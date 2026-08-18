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
pip install -r requirements.txt
flask --app run.py run --debug
```

Disponible en `http://localhost:5000`. La comprobación de estado está en `GET /api/health`.
