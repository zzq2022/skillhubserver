# Domain glossary — skillhubserver

> Product language only. No implementation details.
> Updated during design sessions as terms resolve.

## Product identity

| Term | Definition |
| --- | --- |
| **Skill Hub (技能中心)** | The public-facing catalog of published skills. Default entry point of the product for anonymous visitors. |
| **Console (工作台)** | Not a personal authoring workspace in this product. Logged-in browser use is for account features (e.g. stars) and admin. |
| **Admin (管理后台)** | The authenticated area for administrators: dashboard, review queue, skill moderation, users. |

## Skill lifecycle

| Term | Definition |
| --- | --- |
| **Skill** | A named unit of agent capability owned by one user, identified by `owner/slug` uniqueness. |
| **Private skill** | A skill visible only to its owner (and admins for moderation). Not listed on the Skill Hub. |
| **Published skill** | A skill approved for public listing on the Skill Hub; anyone may browse and download it. |
| **Publish review** | The admin gate between submission and publication: draft → pending review → published or rejected. |
| **External authoring** | Skills are created in **other systems** (notably Hope Agent). This product is a **registry / store**, not an authoring IDE. |
| **Cloud client (Hope)** | External app: user enters server URL + username + password, submits local skill packages for review, syncs publish state, downloads from the Hub. |

## Access model

| Term | Definition |
| --- | --- |
| **Anonymous browse** | Unauthenticated visitors may open the Skill Hub, view published skills, and download packages. |
| **Browser session** | Human users in the Web UI authenticate with session credentials suitable for a browser. |
| **Hope / machine session** | Hope (and similar clients) authenticate with username + password against this server, then call AgentWork-compatible APIs with the tokens that login returns. |
| **Administrator** | A signed-in user who manages accounts, reviews submissions, features/unpublishes skills. |

## Marketplace surface

| Term | Definition |
| --- | --- |
| **Category** | Exactly one primary classification per skill from a fixed product enum. Hub filter rail. Distinct from **tags**. |
| **Tags** | Optional free-form labels; search and card detail, not the primary Hub filter. |
| **Star** | Per-user favorite on a published skill; feeds star count and “most starred” sort. |
| **Download count** | Times a published skill package was downloaded from the Hub. |
| **View count** | Times a published skill detail was opened on the Hub. |
| **Featured** | Admin-curated highlight; dedicated Hub section and sort. |
| **Trending** | Hub sort by recent engagement (formula is a later design detail). |
| **Marketplace stats** | Aggregate Hub figures (published skills, stars, downloads). |

## Resolved product decisions

1. **Parity target**: Chase AgentWork marketplace product surface (not reskin-only).
2. **Landing**: Skill Hub is unauthenticated default home (`/`).
3. **Discovery depth (phase 1)**: Full discovery — categories, five sorts (trending / top downloads / new / most starred / featured), stars, download & view counts, featured, marketplace stats.
4. **Category model**: Fixed category enum + free-form tags; existing skills default to `general`.
5. **Visual language**: Full-app dark console aligned with AgentWork; product name/logo remain skillhubserver.
6. **Implementation path (Web)**: Selectively port AgentWork client pages/layouts; API/auth adapted to this server; no monorepo shared packages, no desktop bridge.
7. **No Web My Skills**: Browser has no personal skill inventory/editor. Hope owns “my skills” and submit UX.
8. **Content supply**: Hope (and peers) upload via HTTP; Web UI is discovery + admin only.
9. **Publish gate**: After upload/submit, only Admin approve lists a skill on the Hub; reject/unpublish remain admin tools.
10. **Admin surface**: Dashboard + Review + Skill management + Users.
11. **Primary external client**: Hope Agent — URL + username + password.
12. **Wire protocol**: AgentWork-compatible HTTP surface on this server so Hope can connect without rewriting its client; Web keeps `/api/v1` Session + CSRF.
13. **Dual channels**: Browser session vs Hope Bearer (AgentWork-shaped routes); one internal domain model.
14. **Delivery order**: First Hope protocol + review gate (end-to-end submit → approve → downloadable); then dark Hub + full discovery + Admin chrome. If scope slips, cut discovery polish before cutting the Hope path.

## Out of product UI (explicit non-goals for Web)

- In-browser SKILL.md authoring / multi-file workspace
- Desktop sync, AI writing assistants
- Personal “My Skills” cabinet on this Web app
