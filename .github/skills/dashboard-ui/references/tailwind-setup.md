# Tailwind CSS Setup with Vite

## Installation

```bash
npm install -D tailwindcss @tailwindcss/vite
```

## Vite Config

```ts
// vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
})
```

## CSS Entry Point

```css
/* src/index.css */
@import "tailwindcss";
```

## Import in main.tsx

```tsx
import './index.css'
```

This uses Tailwind CSS v4 with the Vite plugin — no `tailwind.config.js` needed.
