import 'dotenv/config.js';
import express from 'express';
import path from 'path';
import { fileURLToPath } from 'url';
import fs from 'fs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ limit: '50mb', extended: true }));

// CORS
app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*');
  res.header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.header('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  if (req.method === 'OPTIONS') {
    return res.sendStatus(200);
  }
  next();
});

// Serve static HTML files as routes
const routes = {
  '/': 'index.html',
  '/playbook': 'playbook.html',
  '/hormozi': 'hormozi.html',
  '/ecom-king': 'ecom-king.html',
  '/pinterest': 'pinterest.html',
  '/roi': 'roi.html',
  '/content': 'content.html',
  '/privacy': 'privacy.html',
};

Object.entries(routes).forEach(([route, file]) => {
  app.get(route, (req, res) => {
    res.sendFile(path.join(__dirname, file));
  });
});

// Helper: Convert Vercel Response format to Express
function vercelToExpress(req, res) {
  return new Proxy(res, {
    get: (target, prop) => {
      if (prop === 'json') {
        return (data) => target.json(data);
      }
      if (prop === 'status') {
        return (code) => {
          target.statusCode = code;
          return target;
        };
      }
      return Reflect.get(target, prop);
    }
  });
}

// Dynamic API handler loading
async function loadHandlers() {
  const apiDir = path.join(__dirname, 'api');
  const handlers = {};
  
  if (fs.existsSync(apiDir)) {
    const files = fs.readdirSync(apiDir).filter(f => f.endsWith('.js'));
    
    for (const file of files) {
      const route = `/api/${file.replace('.js', '')}`;
      try {
        const module = await import(`./api/${file}`);
        const handler = module.default;
        
        app.post(route, async (req, res) => {
          try {
            const result = await handler({ method: 'POST', body: req.body, url: req.url }, vercelToExpress(req, res));
            if (!res.headersSent) {
              res.json(result);
            }
          } catch (error) {
            console.error(`[ERROR] ${route}:`, error.message);
            res.status(500).json({ error: error.message });
          }
        });
        
        app.get(route, async (req, res) => {
          try {
            const result = await handler({ method: 'GET', url: req.url }, vercelToExpress(req, res));
            if (!res.headersSent) {
              res.json(result);
            }
          } catch (error) {
            console.error(`[ERROR] ${route}:`, error.message);
            res.status(500).json({ error: error.message });
          }
        });
        
        handlers[file] = 'loaded';
      } catch (error) {
        handlers[file] = `[SKIP] ${error.message.substring(0, 50)}`;
      }
    }
  }
  
  return handlers;
}

// SPA fallback
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'index.html'));
});

// Startup
async function start() {
  try {
    const handlers = await loadHandlers();
    const loaded = Object.values(handlers).filter(v => v === 'loaded').length;
    const skipped = Object.values(handlers).length - loaded;
    
    app.listen(PORT, () => {
      console.log(`\n${'═'.repeat(60)}`);
      console.log(`ShipStack AI — Local Express Server`);
      console.log(`${'═'.repeat(60)}`);
      console.log(`✓ Server listening on port ${PORT}`);
      console.log(`✓ API handlers loaded: ${loaded}/${Object.keys(handlers).length}`);
      if (skipped > 0) console.log(`  (${skipped} handlers skipped due to missing deps)`);
      console.log(`✓ Quinn Bridge: ${process.env.QUINN_ENDPOINT || 'http://localhost:8765'}`);
      console.log(`\nStatic routes:`);
      Object.keys(routes).forEach(route => {
        console.log(`  ${route === '/' ? '  GET  /' : `  GET  ${route}`}`);
      });
      console.log(`\n${'═'.repeat(60)}\n`);
    });
  } catch (error) {
    console.error('Failed to start server:', error);
    process.exit(1);
  }
}

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log('Shutting down gracefully...');
  process.exit(0);
});

start();
