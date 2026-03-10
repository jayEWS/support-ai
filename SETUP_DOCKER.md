# Docker Desktop Installation & VS Code Dev Container Setup

## 🐳 **Step 1: Install Docker Desktop**

1. **Download Docker Desktop for Windows**:
   - Visit: https://www.docker.com/products/docker-desktop/
   - Click "Download Docker Desktop for Windows"
   - Run the installer as Administrator

2. **Installation Requirements**:
   - Enable WSL 2 (Windows Subsystem for Linux 2)
   - Enable Hyper-V (will be prompted during installation)
   - Restart your computer when prompted

3. **Post-Installation Setup**:
   ```powershell
   # Verify Docker installation
   docker --version
   docker-compose --version
   
   # Test Docker is working
   docker run hello-world
   ```

## 🔧 **Step 2: Configure Docker for Development**

1. **Open Docker Desktop Settings**:
   - Right-click Docker Desktop system tray icon
   - Click "Settings"

2. **Recommended Settings**:
   - **General**: Enable "Start Docker Desktop when you log in"
   - **Resources > Advanced**: 
     - CPUs: 4 (if available)
     - Memory: 6GB (minimum 4GB)
   - **Docker Engine**: Add to config:
     ```json
     {
       "builder": {
         "gc": {
           "enabled": true,
           "defaultKeepStorage": "20GB"
         }
       }
     }
     ```

## 🚀 **Step 3: Start VS Code Dev Container**

1. **Open Project in VS Code**:
   ```powershell
   cd D:\Project\support-ai
   code .
   ```

2. **Reopen in Container**:
   - Press `Ctrl+Shift+P`
   - Type "Dev Containers: Reopen in Container"
   - Select it and wait for container to build

3. **Alternative Method**:
   - Look for "Reopen in Container" notification popup
   - Click the popup when it appears

## 📋 **Step 4: Available VS Code Tasks**

Once Docker is installed, use these tasks:

| Task | Shortcut | Purpose |
|------|----------|---------|
| **🐳 Build Enterprise Stack** | `Ctrl+Shift+P` → Tasks → Build | Build all containers |
| **🚀 Start Enterprise Stack** | `Ctrl+Shift+P` → Tasks → Start | Launch all services |
| **🔍 Show Stack Status** | `Ctrl+Shift+P` → Tasks → Status | Check service health |
| **📊 Show Stack Logs** | `Ctrl+Shift+P` → Tasks → Logs | View real-time logs |
| **🛑 Stop Enterprise Stack** | `Ctrl+Shift+P` → Tasks → Stop | Stop all services |

## 🎯 **Expected Result**

After successful setup, you'll have:

- **FastAPI App**: http://localhost:8000
- **Admin Dashboard**: http://localhost:8000/admin  
- **Grafana**: http://localhost:3000
- **Prometheus**: http://localhost:9090
- **Qdrant**: http://localhost:6333

## 🚨 **Troubleshooting**

### Common Issues:

1. **"Docker not found"**:
   - Restart VS Code after Docker installation
   - Ensure Docker Desktop is running

2. **WSL 2 errors**:
   - Run as Administrator: `wsl --install`
   - Restart computer

3. **Memory issues**:
   - Increase Docker Desktop memory allocation
   - Close other applications

4. **Port conflicts**:
   - Stop IIS: `net stop iisadmin`
   - Stop other services using ports 80, 3000, 9090

### Debug Commands:
```powershell
# Check Docker status
docker info

# Check running containers
docker ps

# Check system resources
docker system df

# Clean up if needed
docker system prune -f
```

## ⏭️ **Next Steps**

1. Install Docker Desktop (link opened in browser)
2. Restart your computer
3. Come back to VS Code and press `Ctrl+Shift+P` → "Dev Containers: Reopen in Container"
4. Use the task `🚀 Start Enterprise Stack` to launch your AI platform

---

**Need help?** The Docker Desktop installer will guide you through WSL 2 setup automatically!