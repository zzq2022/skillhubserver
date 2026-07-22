# ADR 0001: AgentWork-compatible API surface for Hope clients

## Status

Accepted (grilling session 2026-07-22)

## Context

skillhubserver is a self-hosted skill registry and public Skill Hub. Skill **authoring** happens in external apps—especially Hope Agent (`hope-agent-main2`)—not in this server’s Web UI.

Hope’s existing cloud client (`agentwork_client.rs`) already speaks **AgentWork** HTTP shapes:

- `POST /api/auth/login` → `access_token` / `refresh_token`, then `Authorization: Bearer`
- `/api/skillhub/public`, `/private`, `review-submissions`, download, etc.

skillhubserver today exposes a different contract:

- `/api/v1/*` with Session cookie + CSRF
- Hub under `/api/v1/hub/*`, import/export and skills CRUD under `/api/v1/...`

Without a compatibility decision, Hope cannot use “server URL + username + password” against this server as the user expects.

## Decision

Implement an **AgentWork-compatible HTTP surface** on skillhubserver that maps onto the existing domain model (users, skills, workspace packages, publish review, hub).

- Hope and similar clients use that surface (token login + Bearer + skillhub paths).
- The browser Web UI continues to use `/api/v1` Session + CSRF for Hub, login, and admin.
- One internal model; two access channels.

## Consequences

**Positive**

- Hope can point at this server with minimal or no client rewrite.
- Clear split: authoring client vs registry/store server.
- Existing review and storage logic can be reused behind adapters.

**Negative**

- Two public HTTP dialects to document and test.
- Token issuance/refresh and path aliases add backend scope before/parallel to UI polish.

**Follow-ups**

- Document exact path/field parity vs Hope’s client for login, refresh, private list, review-submissions, public search/detail/download.
- Prefer adapting response shapes at the edge over forking domain rules.
