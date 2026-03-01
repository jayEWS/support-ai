# 🔧 Project Rename Instructions

**From:** `d:\Project\new support`  
**To:** `d:\Project\support-portal-edgeworks`

---

## Method 1: Using Windows File Explorer (Easiest)

1. **Close VS Code completely:**
   - Close all VS Code windows
   - Close any terminals
   - Verify no processes are running

2. **Open Windows File Explorer:**
   - Navigate to `d:\Project\`
   - Right-click on `new support` folder
   - Select `Rename`
   - Type: `support-portal-edgeworks`
   - Press Enter

3. **Reopen in VS Code:**
   - Open VS Code
   - Open folder: `d:\Project\support-portal-edgeworks`

---

## Method 2: Using PowerShell

```powershell
# Stop VS Code and all associated processes
Stop-Process -Name Code -Force -ErrorAction SilentlyContinue
Stop-Process -Name node -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# Rename the folder
Rename-Item -Path "d:\Project\new support" -NewName "support-portal-edgeworks" -Force

# Verify
Get-Item "d:\Project\support-portal-edgeworks"

# Reopen VS Code
& "C:\Program Files\Microsoft VS Code\Code.exe" "d:\Project\support-portal-edgeworks"
```

---

## Method 3: Using Git (Preserves History)

```bash
# This preserves git history for the folder
git mv "d:\Project\new support" "d:\Project\support-portal-edgeworks"
git commit -m "chore: rename project folder to support-portal-edgeworks"
git push origin main
```

---

## ⚠️ Important Notes After Renaming

### 1. Update any absolute paths in your code:

**Search & Replace:**
- Find: `d:\Project\new support`
- Replace: `d:\Project\support-portal-edgeworks`

**Files to check:**
- `.vscode/settings.json` (if exists)
- `docker-compose.yml`
- Any scripts that reference the path

### 2. Update VS Code workspace file (if exists):

```json
{
  "folders": [
    {
      "path": "d:\\Project\\support-portal-edgeworks"
    }
  ]
}
```

### 3. Update Python virtual environment (if needed):

```bash
# Activate the new venv
cd "d:\Project\support-portal-edgeworks"
.\.venv\Scripts\Activate.ps1

# Or recreate it if paths are embedded
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

---

**After Renaming:** All deployment fixes have been completed! See the deployment guides for next steps.
