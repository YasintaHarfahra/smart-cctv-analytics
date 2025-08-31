#!/usr/bin/env python3
"""
Setup script untuk Object Detection CCTV
"""

import os
import sys
import subprocess
import platform

def run_command(command, description):
    """Run command and handle errors"""
    print(f"\n🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} berhasil")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} gagal: {e}")
        print(f"Error output: {e.stderr}")
        return False

def check_python_version():
    """Check if Python version is compatible"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 3.8+ required")
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro} detected")
    return True

def install_backend_dependencies():
    """Install backend Python dependencies"""
    os.chdir("backend")
    
    # Install pip dependencies
    if not run_command("pip install -r requirements.txt", "Installing Python dependencies"):
        return False
    
    # Download YOLO model
    if not run_command("python download_model.py", "Downloading YOLO model"):
        return False
    
    os.chdir("..")
    return True

def install_frontend_dependencies():
    """Install frontend Node.js dependencies"""
    os.chdir("frontend")
    
    if not run_command("npm install", "Installing Node.js dependencies"):
        return False
    
    os.chdir("..")
    return True

def check_system_requirements():
    """Check system requirements"""
    print("\n🔍 Checking system requirements...")
    
    # Check Python
    if not check_python_version():
        return False
    
    # Check pip
    try:
        import pip
        print("✅ pip available")
    except ImportError:
        print("❌ pip not available")
        return False
    
    # Check Node.js
    try:
        result = subprocess.run("node --version", shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Node.js {result.stdout.strip()} available")
        else:
            print("❌ Node.js not available")
            return False
    except:
        print("❌ Node.js not available")
        return False
    
    # Check npm
    try:
        result = subprocess.run("npm --version", shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ npm {result.stdout.strip()} available")
        else:
            print("❌ npm not available")
            return False
    except:
        print("❌ npm not available")
        return False
    
    return True

def main():
    """Main setup function"""
    print("🚀 Smart CCTV Analytics - Object Detection Setup")
    print("=" * 50)
    
    # Check system requirements
    if not check_system_requirements():
        print("\n❌ System requirements not met. Please install missing dependencies.")
        sys.exit(1)
    
    # Install backend dependencies
    if not install_backend_dependencies():
        print("\n❌ Backend setup failed")
        sys.exit(1)
    
    # Install frontend dependencies
    if not install_frontend_dependencies():
        print("\n❌ Frontend setup failed")
        sys.exit(1)
    
    print("\n🎉 Setup completed successfully!")
    print("\n📋 Next steps:")
    print("1. Start backend: cd backend && uvicorn app.main:app --reload")
    print("2. Start frontend: cd frontend && npm run dev")
    print("3. Open browser: http://localhost:3001")
    print("4. Navigate to CCTV detail and click 'Start Detection'")
    
    print("\n📚 For more information, see README_OBJECT_DETECTION.md")

if __name__ == "__main__":
    main()
