const { app, BrowserWindow, Menu, shell, dialog, ipcMain } = require('electron');
const path = require('path');
const isDev = require('electron-is-dev');
const { spawn, exec } = require('child_process');

let mainWindow;
let backendProcess = null;
let isBackendRunning = false;

// Check if backend is running
async function checkBackend() {
  return new Promise((resolve) => {
    const http = require('http');
    const req = http.get('http://localhost:8000/api/agent/state', (res) => {
      resolve(res.statusCode === 200);
    });
    req.on('error', () => resolve(false));
    req.setTimeout(2000, () => {
      req.destroy();
      resolve(false);
    });
  });
}

// Start backend process
async function startBackend() {
  if (isBackendRunning) return true;
  
  try {
    console.log('Starting Cold Outreach Agent backend...');
    
    // Use a more robust approach to handle paths with spaces
    const projectRoot = path.join(__dirname, '..', '..');
    const startScript = path.join(projectRoot, 'docker-start-simple.bat');
    
    backendProcess = spawn('cmd', ['/c', `cd /d "${projectRoot}" && "${startScript}"`], {
      detached: false,
      stdio: 'pipe',
      shell: true
    });
    
    backendProcess.stdout.on('data', (data) => {
      console.log(`Backend: ${data}`);
    });
    
    backendProcess.stderr.on('data', (data) => {
      console.error(`Backend Error: ${data}`);
    });
    
    // Wait for backend to be ready
    let attempts = 0;
    while (attempts < 30) {
      await new Promise(resolve => setTimeout(resolve, 2000));
      if (await checkBackend()) {
        isBackendRunning = true;
        return true;
      }
      attempts++;
    }
    
    throw new Error('Backend failed to start after 60 seconds');
    
  } catch (error) {
    console.error('Failed to start backend:', error);
    return false;
  }
}

// Stop backend process
function stopBackend() {
  if (backendProcess) {
    backendProcess.kill('SIGTERM');
    backendProcess = null;
    isBackendRunning = false;
  }
}

function createWindow() {
  // Create the browser window
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1200,
    minHeight: 700,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    },
    icon: path.join(__dirname, 'icon.png'),
    title: 'Cold Outreach Agent',
    show: false // Don't show until ready
  });

  // Create application menu
  const template = [
    {
      label: 'File',
      submenu: [
        {
          label: 'Restart Backend',
          click: async () => {
            stopBackend();
            isBackendRunning = false;
            const success = await startBackend();
            if (success) {
              mainWindow.reload();
            } else {
              dialog.showErrorBox('Error', 'Failed to restart backend');
            }
          }
        },
        { type: 'separator' },
        {
          label: 'Exit',
          accelerator: 'CmdOrCtrl+Q',
          click: () => {
            app.quit();
          }
        }
      ]
    },
    {
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'forceReload' },
        { role: 'toggleDevTools' },
        { type: 'separator' },
        { role: 'resetZoom' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { type: 'separator' },
        { role: 'togglefullscreen' }
      ]
    },
    {
      label: 'Help',
      submenu: [
        {
          label: 'About',
          click: () => {
            dialog.showMessageBox(mainWindow, {
              type: 'info',
              title: 'About Cold Outreach Agent',
              message: 'Cold Outreach Agent v1.0.0',
              detail: 'A powerful tool for managing cold outreach campaigns with human oversight and safety controls.'
            });
          }
        }
      ]
    }
  ];

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);

  // Show loading screen first
  mainWindow.loadFile(path.join(__dirname, 'loading.html'));
  mainWindow.show();

  // Start backend and then load main app
  startBackend().then((success) => {
    if (success) {
      // Load the app from localhost
      mainWindow.loadURL('http://localhost:8000');
    } else {
      // Show error page
      mainWindow.loadFile(path.join(__dirname, 'error.html'));
    }
  });

  // Handle external links
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// App event handlers
app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  stopBackend();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

app.on('before-quit', () => {
  stopBackend();
});

// IPC handlers
ipcMain.handle('check-backend', checkBackend);
ipcMain.handle('restart-backend', async () => {
  stopBackend();
  isBackendRunning = false;
  return await startBackend();
});