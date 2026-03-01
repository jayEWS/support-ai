#!/usr/bin/env python3
"""
Helper script to rename project folder and update references
This script safely handles renaming with proper error handling
"""

import os
import sys
import shutil
from pathlib import Path

def rename_project_folder():
    """
    Rename project from 'new support' to 'support-portal-edgeworks'
    """
    
    old_path = Path("d:\\Project\\new support")
    new_path = Path("d:\\Project\\support-portal-edgeworks")
    
    print("🔧 Support Portal Edgeworks - Project Rename Helper")
    print("=" * 60)
    print()
    
    # Check if old folder exists
    if not old_path.exists():
        print(f"❌ Error: Old folder not found at {old_path}")
        print("   Make sure you're in the right location")
        return False
    
    # Check if new folder already exists
    if new_path.exists():
        print(f"❌ Error: New folder already exists at {new_path}")
        return False
    
    print(f"📁 Old path: {old_path}")
    print(f"📁 New path: {new_path}")
    print()
    
    # Check for running processes
    print("🔍 Checking for locked processes...")
    try:
        import psutil
        locked_processes = []
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if 'Code' in proc.info['name'] or 'python' in proc.info['name']:
                    locked_processes.append(f"  - {proc.info['name']} (PID {proc.info['pid']})")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        if locked_processes:
            print("⚠️  Found running processes that may lock the folder:")
            for proc in locked_processes:
                print(proc)
            print("\n📝 Recommendation: Close VS Code and any Python processes before renaming")
            response = input("\n➡️  Continue anyway? (y/n): ").lower().strip()
            if response != 'y':
                return False
    except ImportError:
        print("   (psutil not installed, skipping process check)")
    
    # Attempt rename
    print("\n🔄 Renaming folder...")
    try:
        old_path.rename(new_path)
        print(f"✅ Successfully renamed to: {new_path}")
        print()
        
        # Update common configuration files
        print("📝 Updating configuration references...")
        
        # Check for files that might reference the old path
        config_files = [
            "render.yaml",
            "docker-compose.yml",
            ".vscode/settings.json",
        ]
        
        updated_files = 0
        for config_file in config_files:
            file_path = new_path / config_file
            if file_path.exists():
                try:
                    content = file_path.read_text()
                    if "new support" in content:
                        new_content = content.replace("new support", "support-portal-edgeworks")
                        file_path.write_text(new_content)
                        print(f"  ✓ Updated: {config_file}")
                        updated_files += 1
                except Exception as e:
                    print(f"  ⚠️  Could not update {config_file}: {e}")
        
        if updated_files > 0:
            print(f"\n✅ Updated {updated_files} configuration file(s)")
        
        print("\n✨ Rename completed successfully!")
        print("\n📋 Next steps:")
        print("  1. Close any VS Code windows")
        print("  2. Reopen VS Code with the new folder path")
        print("  3. Run: python main.py")
        print("  4. Verify with: curl http://localhost:8000/health")
        print("\n🚀 Ready to deploy! See PRODUCTION_DEPLOYMENT_GUIDE.md for next steps")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during rename: {e}")
        print("\n📝 Alternative: Use Windows File Explorer or PowerShell")
        print("   See RENAME_INSTRUCTIONS.md for manual steps")
        return False


def update_virtual_environment():
    """
    Update virtual environment references if needed
    """
    print("\n🔧 Checking virtual environment...")
    
    venv_path = Path("d:\\Project\\support-portal-edgeworks\\.venv")
    if venv_path.exists():
        print("✓ Virtual environment found at:", venv_path)
        print("\n⚠️  Note: If venv is locked in file paths, you may need to:")
        print("  1. Deactivate current venv")
        print("  2. Delete .venv folder")
        print("  3. Recreate with: python -m venv .venv")
        print("  4. Reactivate and reinstall: pip install -r requirements.txt")
    
    return True


if __name__ == "__main__":
    try:
        success = rename_project_folder()
        if success:
            update_virtual_environment()
            sys.exit(0)
        else:
            print("\n❌ Rename failed. See instructions above.")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n❌ Rename cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
