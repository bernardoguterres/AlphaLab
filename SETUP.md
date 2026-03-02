# AlphaLab Setup Guide

Complete installation and setup guide for both web and desktop versions.

---

## Prerequisites

- **Python 3.9+** (backend)
- **Node.js 18+** (frontend)
- **Rust** (desktop app only - optional)

---

## Quick Start

### 1. Backend Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

✅ Backend running at http://127.0.0.1:5000

### 2. Frontend Setup (Web)

```bash
cd frontend
npm install
npm run dev
```

✅ Frontend running at http://localhost:8080

### 3. Desktop App Setup (Optional)

**Prerequisites (one-time):**

**macOS:**
```bash
# Accept Xcode license (required for Rust compilation)
sudo xcodebuild -license

# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env

# Verify installation
rustc --version
```

**Windows/Linux:**
```bash
# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env
```

**Install Node.js dependencies:**
```bash
cd frontend
npm install
```

---

## Running the Application

### Web Version

```bash
# Terminal 1 - Backend
cd backend && source venv/bin/activate && python run.py

# Terminal 2 - Frontend
cd frontend && npm run dev
```

Open http://localhost:8080 in your browser.

### Desktop Version

```bash
# Terminal 1 - Backend (REQUIRED)
cd backend && source venv/bin/activate && python run.py

# Terminal 2 - Desktop App
cd frontend && npm run tauri:dev
```

App opens in native window with hot-reload enabled.

**Build time:**
- **First build:** 3-5 minutes (compiles all Rust dependencies)
- **Subsequent builds:** 30-60 seconds (incremental compilation)

---

## Building for Production

### Web Build
```bash
cd frontend
npm run build
```
Output: `frontend/dist/` folder

### Desktop Installer Build

```bash
cd frontend
npm run tauri:build
```

**Output location:**
```
frontend/src-tauri/target/release/bundle/
├── dmg/              # macOS installer (~5.5MB)
├── msi/              # Windows installer
└── deb/              # Linux installer
```

**Installing the .dmg (macOS):**
1. Locate: `frontend/src-tauri/target/release/bundle/dmg/AlphaLab_*.dmg`
2. Double-click to open
3. Drag **AlphaLab.app** to **Applications** folder
4. **First launch:** Right-click → Open (to bypass Gatekeeper)
5. After first launch, you can open normally

---

## Desktop App Development

### Making Changes & Rebuilding

When you change frontend code:

```bash
cd frontend

# Option 1: Test changes in development mode (fastest)
npm run tauri:dev

# Option 2: Build new installer
npm run tauri:build
```

**After building:**
1. Uninstall old version: Delete `AlphaLab.app` from Applications
2. Install new .dmg (see steps above)

### Common Customization Tasks

**Update App Version:**
Edit `frontend/src-tauri/tauri.conf.json`:
```json
{
  "productName": "AlphaLab",
  "version": "0.2.0",  // <-- Change this
}
```

**Change App Icon:**
1. Place your icon PNG (1024x1024) in `frontend/src-tauri/icons/`
2. Run: `npm run tauri icon path/to/your-icon.png`
3. Rebuild: `npm run tauri:build`

**Change Window Size:**
Edit `frontend/src-tauri/tauri.conf.json`:
```json
{
  "app": {
    "windows": [{
      "width": 1400,      // <-- Change these
      "height": 900,
      "minWidth": 1200,
      "minHeight": 700
    }]
  }
}
```

**Clean Build (if something breaks):**
```bash
cd frontend
rm -rf src-tauri/target
npm run tauri:build
```

---

## Testing

### Backend Tests (81 tests)
```bash
cd backend
source venv/bin/activate
pytest tests/ -v                    # All tests
pytest tests/test_strategies.py -v # Strategy tests only
pytest tests/ -k "test_name" -v    # Specific test
```

### Frontend Tests
```bash
cd frontend
npm run test        # Run once
npm run test:watch  # Watch mode
```

---

## Troubleshooting

### Backend Issues

**Backend won't start:**
- Check Python 3.9+ installed: `python3 --version`
- Activate venv: `source venv/bin/activate`
- Reinstall deps: `pip install -r requirements.txt`

**Port 5000 in use:**
- Change port in `backend/config.yaml`
- Update API URL in `frontend/src/services/api.ts`

### Frontend Issues

**Frontend can't connect to backend:**
- Check backend running: `curl http://127.0.0.1:5000/api/health`
- Check CORS in `backend/config.yaml` includes `localhost:8080`

**Port 8080 in use:**
- Vite will automatically try port 8081
- Or change port in `frontend/vite.config.ts`

### Desktop App Issues

**"AlphaLab" is damaged and can't be opened:**
- **Solution:** Right-click → Open (first time only)

**Build fails with linker errors:**
```bash
# Re-accept Xcode license (macOS)
sudo xcodebuild -license accept

# Update Rust
rustup update

# Try again
npm run tauri:build
```

**App won't connect to backend:**
1. Make sure backend is running: `cd backend && python run.py`
2. Backend should be on `http://127.0.0.1:5000`
3. Check `frontend/src/services/api.ts` for correct API URL

**Port 8080 already in use:**
- Tauri config will automatically try port 8081 if 8080 is busy

---

## Quick Command Reference

| Task | Command |
|------|---------|
| **Start backend** | `cd backend && source venv/bin/activate && python run.py` |
| **Start web frontend** | `cd frontend && npm run dev` |
| **Start desktop app** | `cd frontend && npm run tauri:dev` |
| **Build web app** | `cd frontend && npm run build` |
| **Build desktop installer** | `cd frontend && npm run tauri:build` |
| **Run backend tests** | `cd backend && pytest tests/ -v` |
| **Run frontend tests** | `cd frontend && npm run test` |
| **Clean build** | `cd frontend && rm -rf src-tauri/target && npm run tauri:build` |

---

## Project Structure

```
AlphaLab/
├── backend/                    # Python Flask API
│   ├── src/
│   │   ├── data/              # Data fetching, validation, feature engineering
│   │   ├── strategies/        # Trading strategies (MA, RSI, Momentum)
│   │   ├── backtest/          # Backtest engine, portfolio, metrics
│   │   ├── api/               # Flask routes + Pydantic validators
│   │   └── utils/             # Logger, config, exceptions
│   ├── tests/                 # 81 pytest tests
│   ├── config.yaml            # Backend configuration
│   ├── requirements.txt
│   └── run.py
├── frontend/                   # React + TypeScript + Tauri
│   ├── src/
│   │   ├── pages/            # Dashboard, Backtest, Compare, DataManager
│   │   ├── components/       # UI components (shadcn/ui + custom)
│   │   ├── services/         # API client (axios)
│   │   ├── stores/           # Zustand state management
│   │   ├── types/            # TypeScript type definitions
│   │   └── utils/            # Formatters, validators
│   ├── src-tauri/            # Tauri desktop wrapper
│   │   ├── tauri.conf.json  # App configuration
│   │   ├── icons/           # App icons
│   │   └── target/release/bundle/  # 👈 Built installers here
│   ├── package.json
│   ├── vite.config.ts        # Dev server on port 8080
│   └── tailwind.config.ts
├── docs/                       # Technical documentation
│   ├── API.md
│   ├── ARCHITECTURE.md
│   ├── STRATEGIES.md
│   ├── METRICS_GUIDE.md
│   └── TROUBLESHOOTING.md
├── README.md                   # Project overview
├── SETUP.md                    # This file
└── LICENSE                     # MIT License
```

---

## Notes

- **Backend must be running** for both web and desktop versions
- **First Tauri build takes 3-5 min** (downloads and compiles Rust dependencies)
- **Subsequent builds ~30 sec** (incremental compilation)
- **.dmg is only 5.5MB** (Tauri is super lightweight!)
- **Frontend changes** require rebuild, but backend changes work immediately (just restart `python run.py`)
- **Backend runs on port 5000**, frontend dev server on port 8080
- **Tests:** 81 backend tests, all passing

---

For detailed development information, see **README.md**.
