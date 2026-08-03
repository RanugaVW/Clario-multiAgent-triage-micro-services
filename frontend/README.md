# Clario Frontend (Next.js)

The modern, responsive UI for the Clario Ticket Orchestration platform.

## Architecture & Design

Built with **Next.js 14 (App Router)** and **Tailwind CSS**. It uses premium visual elements like glassmorphism, animated gradients, and lucide-react icons to provide an excellent user experience. 

Currently, the frontend directly communicates with the Python ML Sidecar (`http://localhost:8600/process_ticket`) for evaluation purposes. Once the `clario-app` API gateway is complete, API requests will be routed through it.

## Setup and Prerequisites

- Node.js 20+

## Commands

- Install dependencies: `npm install`
- Start development server: `npm run dev` (runs on port 3000)
- Run tests: `npm run test`
- Build for production: `npm run build`

## Testing

The frontend uses **Vitest** and **React Testing Library**. Tests are located in `src/app/__tests__`. They cover successful ticket submission, error handling, and component rendering without relying on live backend services (using fetch mocks).

## CI/CD and Deployment

- Linting, testing, and building are enforced on every PR via `.github/workflows/ci.yml`.
- Deployed to **Vercel** for fast edge rendering.

## Troubleshooting

- **Fetch Errors (Network/CORS):** If you see "Processing Error", ensure the ML Sidecar is actively running locally on port 8600 and CORS is properly configured on the backend.
