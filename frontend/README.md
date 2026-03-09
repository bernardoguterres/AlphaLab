# AlphaLab Frontend

React + TypeScript frontend for the AlphaLab trading strategy backtester.

See the main [README.md](../README.md) for project overview, features, and tech stack details.

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

**Backend Required:** The Flask backend must be running at `http://127.0.0.1:5000` (configure in `src/services/api.ts`).


## Troubleshooting

**Tauri-specific issues:**
- First build takes 2-3 minutes (compiles 400+ Rust dependencies)
- macOS: Accept Xcode license first: `sudo xcodebuild -license`
- Clean Rust build cache: `rm -rf src-tauri/target`
- Port 8080 in use: Vite auto-switches to 8081

See [../docs/TROUBLESHOOTING.md](../docs/TROUBLESHOOTING.md) for more issues and [../README.md](../README.md) for full project documentation.
