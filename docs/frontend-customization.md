# Frontend Customization Guide

How to modify the AgentForge frontend template for your agent's specific needs.

The frontend is a **template, not a framework**. It provides the structure, component library, API integration patterns, and styling foundation. Modify it freely — the goal is a working starting point, not a finished product.

---

## Project Structure

```
frontend/
├── index.html                    # HTML entry point
├── vite.config.ts                # Vite config (plugins, dev proxy to backend)
├── tsconfig.json                 # TypeScript project references
│
└── src/
    ├── main.tsx                  # App entry point (QueryClientProvider)
    ├── App.tsx                   # Root component
    ├── index.css                 # Global styles + Tailwind + shadcn/ui CSS variables
    │
    ├── types/
    │   └── api.ts                # TypeScript interfaces matching backend schemas
    │
    ├── lib/
    │   ├── api.ts                # API client (fetch wrapper + typed functions)
    │   └── utils.ts              # shadcn/ui cn() utility
    │
    ├── hooks/
    │   ├── useAgent.ts           # React Query mutation for POST /api/ask
    │   └── useWorkflow.ts        # React Query mutation for POST /api/research
    │
    └── components/
        ├── ui/                   # shadcn/ui components (auto-generated, do not edit)
        │   ├── button.tsx
        │   ├── input.tsx
        │   ├── card.tsx
        │   ├── badge.tsx
        │   ├── scroll-area.tsx
        │   └── skeleton.tsx
        │
        ├── chat/                 # Chat interface (primary area to customize)
        │   ├── ChatInterface.tsx  # Orchestrates messages, state, and API calls
        │   ├── MessageBubble.tsx  # Renders individual user/assistant messages
        │   ├── SourceCard.tsx     # Renders source citations below messages
        │   └── InputBar.tsx       # Text input + send button
        │
        └── layout/
            ├── Header.tsx         # App header bar
            └── MainLayout.tsx     # Page layout wrapper
```

---

## Development Setup

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server starts at `http://localhost:5173` and proxies `/api` requests to the FastAPI backend at `http://localhost:8000`. The backend must be running for API calls to work.

---

## Changing the Chat UI

### Modifying Message Display

Edit `src/components/chat/MessageBubble.tsx` to change how messages are rendered. The component receives a `message` object with `role`, `content`, and optional `sources`.

To add a confidence score display for workflow responses, add a `confidence` field to the `Message` interface and render it in the bubble.

### Customizing the Input Bar

Edit `src/components/chat/InputBar.tsx` to extend the input. Common additions:

- **Mode switcher** — toggle between the single agent (`/api/ask`) and research workflow (`/api/research`)
- **User ID field** — expose a user ID input for the memory-aware agent (`/api/ask/memory`)
- **Keyboard shortcut** — the template already submits on Enter; add Shift+Enter for newlines

### Changing the Layout

Edit `src/components/layout/Header.tsx` to add navigation, branding, or status indicators. Edit `src/components/layout/MainLayout.tsx` to adjust the overall page structure (e.g., add a sidebar for conversation history).

---

## Connecting New API Endpoints

Follow these four steps whenever you add a new backend endpoint.

### Step 1: Add TypeScript Types

Add interfaces to `src/types/api.ts` that mirror your new Pydantic schemas:

```typescript
// Example: a new summarization endpoint
export interface SummarizeRequest {
  topic: string;
  max_length?: number;
}

export interface SummarizeResponse {
  summary: string;
  sources: Source[];
}
```

### Step 2: Add an API Client Function

Add a typed function to `src/lib/api.ts`. Use the existing `request()` helper — it handles base URL, JSON headers, and error wrapping:

```typescript
import type { SummarizeRequest, SummarizeResponse } from "../types/api";

export async function summarizeTopic(
  data: SummarizeRequest,
): Promise<SummarizeResponse> {
  return request<SummarizeResponse>("/summarize", {
    method: "POST",
    body: JSON.stringify(data),
  });
}
```

### Step 3: Create a React Query Hook

Create `src/hooks/useSummarize.ts`:

```typescript
import { useMutation } from "@tanstack/react-query";
import { summarizeTopic } from "../lib/api";
import type { SummarizeRequest, SummarizeResponse } from "../types/api";

export function useSummarize() {
  return useMutation<SummarizeResponse, Error, SummarizeRequest>({
    mutationFn: (data) => summarizeTopic(data),
  });
}
```

### Step 4: Use the Hook in a Component

```typescript
import { useSummarize } from "../../hooks/useSummarize";

function SummarizePanel() {
  const summarize = useSummarize();

  const handleSubmit = async (topic: string) => {
    const result = await summarize.mutateAsync({ topic });
    console.log(result.summary);
  };

  return (
    <div>
      {summarize.isPending && <p>Summarizing...</p>}
      {summarize.isError && <p>Error: {summarize.error.message}</p>}
    </div>
  );
}
```

---

## Styling

### Tailwind CSS v4

This project uses Tailwind CSS v4, which requires no configuration files. Use Tailwind utility classes directly in JSX. All customization is done via CSS variables.

### Changing the Color Scheme

Open `src/index.css`. The shadcn/ui CSS variables control the theme:

```css
:root {
  --background: oklch(1 0 0);
  --foreground: oklch(0.145 0 0);
  --primary: oklch(0.205 0 0);
  /* ... */
}
```

Modify these variables to change the color scheme globally. The shadcn/ui [Themes](https://ui.shadcn.com/themes) page provides pre-built theme configurations you can paste in directly.

### Adding shadcn/ui Components

```bash
cd frontend
npx shadcn@latest add dialog
npx shadcn@latest add dropdown-menu
npx shadcn@latest add tabs
```

Components are added to `src/components/ui/`. Browse all available components at https://ui.shadcn.com/docs/components.

---

## Adding Pages

The template ships as a single-page chat interface with no router. To add multiple pages:

**1. Install React Router:**

```bash
cd frontend
npm install react-router-dom
```

**2. Update `src/App.tsx`:**

```tsx
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { MainLayout } from "./components/layout/MainLayout";
import { ChatInterface } from "./components/chat/ChatInterface";
import { SettingsPage } from "./pages/SettingsPage";

export default function App() {
  return (
    <BrowserRouter>
      <MainLayout>
        <Routes>
          <Route path="/" element={<ChatInterface />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </MainLayout>
    </BrowserRouter>
  );
}
```

**3. Create page components in `src/pages/`.**

---

## Building for Production

**Local build** — outputs to `frontend/dist/`:

```bash
cd frontend
npm run build
```

The build script runs TypeScript compilation (`tsc -b`) followed by the Vite production build. Fix any TypeScript errors before the build will succeed.

**Docker build** — builds the image for deployment:

```bash
docker build -t agentforge-frontend ./frontend
```

The Docker image uses a multi-stage build: Node 20 compiles the assets, then nginx serves them from `dist/`. The nginx config handles SPA routing (all routes return `index.html`) and proxies `/api/` requests to the backend container.

**Preview the production build locally:**

```bash
cd frontend
npm run preview
```

This serves the built `dist/` folder at `http://localhost:4173`.
