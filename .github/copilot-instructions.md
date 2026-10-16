# Project Guidelines

## Stack

- **Backend**: FastAPI (Python) + Uvicorn
- **Frontend**: React 19 + TypeScript + Vite + Tailwind CSS 4 + React Router DOM 7
- **Package manager**: pnpm

## Run Commands

### Backend

```bash
cd backend
python -m venv .venv

#for mac
source .venv/bin/activate

#for widows


pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm dev
```

## Code Conventions

- Use FastAPI dependency injection and Pydantic models for request/response validation.
- Prefer TypeScript strict mode; avoid `any`.
- Use Tailwind utility classes for styling; keep components in `frontend/src/`.
- Add new routes in `frontend/src/App.tsx` and place page components under `frontend/src/pages/`.
- Keep API client calls in a dedicated service module under `frontend/src/`.

## API/Frontend Integration

- Backend base URL in dev: `http://localhost:8000`.
- Use environment variables (e.g., `VITE_API_BASE_URL`) for API URLs; prefix frontend env vars with `VITE_`.
- Use `fetch` or a lightweight HTTP client; avoid adding heavy dependencies without reason.

## Project Notes

- Project name is a placeholder ("GyrosProject") and will be renamed later.
