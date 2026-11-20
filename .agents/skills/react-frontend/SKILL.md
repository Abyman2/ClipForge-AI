---
name: react-frontend
description: >-
  Use this skill when developing, styling, or debugging the React frontend, TypeScript
  interfaces, Tailwind dark-theme UI, video player components, or SSE progress listeners.
---

# React Frontend Development Skill

This skill governs the development of the ClipForge AI frontend using React 18+, TypeScript, Vite, and Tailwind CSS.

## When to Use This Skill
- Building or modifying UI components in `frontend/src/`.
- Implementing video inspection, trim adjustment, or dual-preview players.
- Connecting Server-Sent Events (SSE) for real-time pipeline progress bars.
- Managing user settings (LLM API keys, model selection, hardware profile).

## Step-by-Step Procedure

1. **Scaffold or Inspect Component:**
   - Place components in `frontend/src/components/` organized by domain (`video/`, `dashboard/`, `settings/`).
   - Define strict TypeScript interfaces for all props and state.

2. **Implement Dark-Themed Tailwind Styling:**
   - Use the approved dark palette:
     - Backgrounds: `bg-slate-950` / `bg-slate-900`
     - Borders: `border-slate-800`
     - Text: `text-slate-100` / `text-slate-400`
     - Accents: `text-amber-400` / `bg-amber-500` (highlights and viral scores)
   - Ensure high contrast and clean typography.

3. **Integrate Real-Time SSE Progress:**
   - Use a custom `useJobEvents` hook to listen to `/api/jobs/{id}/events`.
   - Update phase indicators (`Extracting Audio`, `Transcribing`, `Discovering Highlights`, `Rendering`).
   - Display a clean percentage progress bar and recent status messages.

4. **Implement Dual-Preview Video Studio:**
   - Provide a review interface where users can preview the candidate clip.
   - Show original 16:9 widescreen alongside a simulated 9:16 vertical crop window.
   - Include interactive trim handles to adjust start/end boundaries if needed.

5. **Handle API Settings Securely:**
   - In Settings, provide fields for `Base URL`, `API Protocol` (dropdown: Anthropic / OpenAI), `Model Name`, and `API Key`.
   - Mask the API key input (`type="password"`).
   - Provide a "Test Connection" button that validates credentials against the backend.

## Technical Standards
- **No Direct Polling:** Use Server-Sent Events (`EventSource`) for real-time updates.
- **Strict Type Safety:** Mirror backend Pydantic models in `frontend/src/types/api.ts`.
- **Keyboard Shortcuts:** Support Space (Play/Pause), Left/Right Arrow (Seek 1s), and `[` / `]` for setting in/out points.

## Common Mistakes to Avoid
- **Uncontrolled Re-renders:** Triggering heavy state updates on every video `timeupdate` event. Throttle or decouple playback position from root state.
- **Exposing Raw Secrets in State:** Caching raw API keys in local storage if not masked.
- **Ignoring Backend Errors:** Failing to display clear toast notifications when backend pipeline tasks fail.

## Verification Checklist
- [ ] TypeScript compiles cleanly with zero errors (`tsc --noEmit`).
- [ ] Dark theme renders cleanly across all views.
- [ ] SSE progress bar updates smoothly without page reloads.
- [ ] Video playback and timeline trimming function accurately.
- [ ] API settings save cleanly to the backend.

