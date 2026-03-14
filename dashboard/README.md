# Halifax Energy Forecasting Dashboard

React + Vite frontend for the Halifax Area Energy Demand Forecasting system.

## Features

- **Interactive Map:** Leaflet-based map showing Halifax zones with predicted/actual load
- **Forecast Charts:** Recharts visualizations comparing predictions vs actuals
- **Performance Metrics:** Real-time model performance (RMSE, SI%) tracking
- **Live Data:** WebSocket integration for streaming actual load data
- **Model Management:** Trigger model training and view artifacts
- **Data Explorer:** Browse and analyze historical load data

## Tech Stack

- **React 18** — UI library
- **Vite** — Build tool and dev server
- **React Router** — Client-side routing
- **Leaflet** — Interactive maps
- **Recharts** — Data visualization
- **Axios** — HTTP client
- **date-fns** — Date manipulation
- **Lucide React** — Icon library

## Quick Start

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## Development

### Environment Variables

Create `.env` file (optional):

```env
VITE_API_URL=http://localhost:8000
```

### Project Structure

```
dashboard/
├── src/
│   ├── components/       # Reusable components
│   │   ├── Layout.jsx    # App layout with sidebar/header
│   │   ├── Sidebar.jsx   # Navigation sidebar
│   │   ├── Header.jsx    # Top header with status
│   │   ├── MapView.jsx   # Leaflet map component
│   │   ├── ForecastChart.jsx     # Recharts forecast viz
│   │   └── PerformanceMetrics.jsx  # Model metrics
│   ├── pages/           # Page components
│   │   ├── Dashboard.jsx  # Main dashboard page
│   │   ├── Models.jsx    # Model management page
│   │   └── Data.jsx      # Data explorer page
│   ├── utils/
│   │   └── api.js       # API client functions
│   ├── App.jsx          # Root component
│   ├── main.jsx         # Entry point
│   └── index.css        # Global styles
├── package.json
├── vite.config.js
└── index.html
```

## API Integration

The dashboard connects to the FastAPI backend at `http://localhost:8000`.

Vite proxy configuration (see `vite.config.js`):
- `/api/*` → proxied to backend
- `/ws/*` → WebSocket proxy for live data

## Available Scripts

- `npm run dev` — Start development server (port 5173)
- `npm run build` — Build for production
- `npm run preview` — Preview production build
- `npm run lint` — Run ESLint

## Deployment

### Build for Production

```bash
npm run build
```

Outputs to `dist/` directory.

### Serve with Nginx

```nginx
server {
    listen 80;
    server_name your-domain.com;

    root /path/to/dashboard/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    location /ws {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
    }
}
```

## Customization

### Adding New Pages

1. Create page component in `src/pages/`
2. Add route in `src/App.jsx`
3. Add navigation link in `src/components/Sidebar.jsx`

### Styling

- Global styles: `src/index.css`
- Component-specific: Co-located `.css` files
- CSS variables defined in `:root` (see `index.css`)

### API Endpoints

Add new API functions in `src/utils/api.js`:

```javascript
export const getMyData = async (params = {}) => {
  const response = await api.get('/api/my-endpoint', { params })
  return response.data
}
```

## Troubleshooting

### Map Not Loading

**Issue:** Blank map or tiles not loading

**Solution:** Check Leaflet CSS is imported in `index.html`:
```html
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
```

### API Connection Errors

**Issue:** `Failed to fetch` errors

**Solution:**
1. Verify backend is running: `http://localhost:8000/health`
2. Check CORS settings in backend (`api/main.py`)
3. Verify proxy config in `vite.config.js`

### WebSocket Not Connecting

**Issue:** Live data not streaming

**Solution:**
1. Check WebSocket URL in `src/utils/api.js`
2. Verify backend WebSocket route is working
3. Check browser console for connection errors

## License

Educational project for NSCC DBAS 3090.

## Author

Dylan Bray
NSCC — Database Administration & Security 3090
March 2026
