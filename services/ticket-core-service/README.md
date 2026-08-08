# Clario API Gateway (Spring Boot)

This directory contains the Spring Boot API Gateway for the Clario platform.

## Architecture

The API Gateway is responsible for:
- User Authentication (JWT validation).
- Persisting incoming tickets to the PostgreSQL database (`status = received`).
- Enforcing Optimistic Locking (`version` field) to prevent conflicting edits during human review.
- Serving as the secure bridge to the Python ML Sidecar (`clario-ml-sidecar`).

## Setup and Prerequisites

- Java 17 or 21
- Maven or Gradle
- PostgreSQL 16

## Environment Variables

Copy the `.env.example` from the root and configure the following:
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_PORT`
- `JWT_SECRET`
- `ORCHESTRATION_URL` (Points to the `clario-ml-sidecar` endpoint)

> **Security Warning:** Never commit real secrets or database passwords.

## Commands

- Run locally: `./gradlew bootRun` (or `mvn spring-boot:run`)
- Run tests: `./gradlew test` (or `mvn test`)

## CI/CD and Deployment

- Tested automatically via GitHub Actions `.github/workflows/ci.yml`.
- Deployed as a containerized service within the `clario_net` private virtual network (e.g., on Render or AWS ECS).

## Troubleshooting

- **Database Connection Failure:** Ensure PostgreSQL is running and credentials match.
- **Sidecar Connection Failure:** Ensure the ML sidecar is running on port 8600.
