# Rule: Frontend Coding Standards

## 1. Technology Foundation

- **Framework:** React 18+ with TypeScript (strict mode enabled).
- **Build Tool:** Vite for fast Hot Module Replacement (HMR).
- **Styling:** Tailwind CSS with a consistent, modern dark theme.
- **Component Design:** Modular, functional components using React hooks. Avoid class components.

## 2. Architecture & State Management

- **Directory Layout:**
  - `src/components/common/`: Reusable primitive components (buttons, modals, badges, inputs).
  - `src/components/video/`: Video player, dual-preview viewer, crop overlay.
  - `src/views/`: Primary route screens (`Dashboard`, `Import`, `Transcript`, `Review`, `Export`, `Settings`).
  - `src/hooks/`: Custom hooks for API data, Server-Sent Events, and media player state.
  - `src/types/`: TypeScript interfaces mirroring backend Pydantic models.
- **Real-Time Updates:** Consume pipeline progress via Server-Sent Events (`EventSource`). Do not poll endpoints in loops.
- **State Separation:** Keep server state (projects, jobs, clips) synchronized via React state/hooks; keep UI transient state (modals open, active tabs, player playhead) strictly local.

## 3. UX & Visual Principles

- **Dark Theme Palette:** Deep grays and slates (`#0F172A`, `#1E293B`) with high-contrast neutral text and vibrant accent colors (amber/yellow or cyan) for active highlights and status badges.
- **Usability Over Decoration:** Prioritize responsive video playback, clear timeline trim handles, and legible captions over heavy CSS animations.
- **Dual-Preview Studio:** In the clip review screen, provide side-by-side or toggled viewing: original 16:9 widescreen vs. vertical 9:16 crop window.
- **Defensive UI:** Disable action buttons during active job processing; show clear progress bars with phase names; display actionable error messages when tasks fail.

