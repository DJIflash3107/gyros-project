# Frontend Guidelines

## Stack
- React 19 + TypeScript + Vite
- Tailwind CSS 4
- React Router DOM 7

## Development First
- Run `npm dev` for local development
- Use `npm build` to verify type-checking and production build before committing
- Keep the dev server feedback loop fast; prefer lightweight dependencies
- Place reusable layout components under `src/components/`
- Place page components under `src/pages/`
- Keep routes in `src/App.tsx` declarative with React Router

## Project Structure
- Pages live under `src/pages/`
- Register new routes in `src/App.tsx`
- Keep API client calls in a dedicated service module under `src/`

## Code Conventions
- TypeScript strict mode is enabled; avoid `any`
- Prefer named exports for reusable components/utils; default exports for page routes are fine
- Use functional components and hooks
- Keep components focused and small; extract when they grow

## Styling
- Use Tailwind utility classes
- Prefer built-in Tailwind spacing, color, and layout utilities over custom CSS

## API Integration
- Use environment variables for API URLs, prefixed with `VITE_`
- Use `fetch` or a lightweight HTTP client; avoid adding heavy dependencies without reason

## Anti-patterns
- Do not add heavy state libraries until plain React state is insufficient
- Avoid premature abstraction; optimize for readability and fast iteration