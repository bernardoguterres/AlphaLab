# AlphaLab Frontend

React + TypeScript frontend for the AlphaLab trading strategy backtester.

## Tech Stack

- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **Tauri** - Desktop app wrapper
- **shadcn/ui** - UI component library
- **Tailwind CSS** - Styling
- **Recharts** - Charts and visualizations
- **Zustand** - State management
- **React Query** - Server state management
- **React Router** - Routing

## Development

### Web Version
```bash
npm install
npm run dev
```
Opens at http://localhost:8080

### Desktop Version (Tauri)
```bash
npm install
npm run tauri:dev
```
Launches native macOS/Windows/Linux app

## Building

### Web Build
```bash
npm run build
```
Output: `dist/` folder

### Desktop Build
```bash
npm run tauri:build
```
Output: `src-tauri/target/release/bundle/`
- macOS: `.dmg` and `.app`
- Windows: `.msi` and `.exe`
- Linux: `.deb` and `.AppImage`

## Project Structure

```
src/
├── components/          # Reusable UI components
│   ├── ui/             # shadcn/ui primitives
│   ├── charts/         # Chart components
│   └── layout/         # Layout components (Header, etc.)
├── pages/              # Page components
│   ├── Dashboard.tsx   # Main dashboard
│   ├── Backtest.tsx    # Backtest configuration & results
│   ├── Compare.tsx     # Strategy comparison
│   └── DataManager.tsx # Data management
├── services/           # API client
│   └── api.ts         # Axios instance and API calls
├── stores/            # Zustand stores
│   └── backtestStore.ts
├── types/             # TypeScript types
│   └── index.ts
├── utils/             # Utility functions
└── App.tsx            # Root component
```

## Available Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start Vite dev server (web) |
| `npm run build` | Build for production (web) |
| `npm run preview` | Preview production build |
| `npm run tauri:dev` | Launch Tauri desktop app |
| `npm run tauri:build` | Build Tauri desktop installer |
| `npm run test` | Run tests |
| `npm run lint` | Lint code |

## Backend Connection

The frontend expects the Flask backend to be running at:
```
http://127.0.0.1:5000
```

Configure in `src/services/api.ts` if you need to change this.

## Environment Variables

No environment variables required for local development.

## Testing

```bash
npm run test        # Run tests once
npm run test:watch  # Run tests in watch mode
```

## Deployment

### Web Deployment
Build with `npm run build` and serve the `dist/` folder with any static hosting service.

### Desktop Distribution
1. Build with `npm run tauri:build`
2. Find installers in `src-tauri/target/release/bundle/`
3. Distribute the appropriate installer for each platform

## Troubleshooting

**Backend connection issues:**
- Ensure backend is running on port 5000
- Check CORS settings in `backend/config.yaml`

**Tauri build fails:**
- Ensure Rust is installed: `rustc --version`
- macOS: Accept Xcode license: `sudo xcodebuild -license`
- Clean build: `rm -rf src-tauri/target && npm run tauri:build`

**Port 8080 in use:**
- Vite will automatically try port 8081
- Or change port in `vite.config.ts`

## More Info

See the main [README.md](../README.md) in the project root for full documentation.
