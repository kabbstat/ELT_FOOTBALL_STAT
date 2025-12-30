#!/usr/bin/env python
"""
Setup Script for Football ELT Pipeline
Automated setup and validation
"""
import os
import sys
from pathlib import Path
import subprocess


class SetupManager:
    """Manage project setup"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.checks_passed = []
        self.checks_failed = []
    
    def print_header(self, text):
        """Print formatted header"""
        print("\n" + "=" * 60)
        print(f"  {text}")
        print("=" * 60)
    
    def print_success(self, text):
        """Print success message"""
        print(f"✅ {text}")
        self.checks_passed.append(text)
    
    def print_error(self, text):
        """Print error message"""
        print(f"❌ {text}")
        self.checks_failed.append(text)
    
    def print_info(self, text):
        """Print info message"""
        print(f"ℹ️  {text}")
    
    def check_python_version(self):
        """Check Python version"""
        self.print_header("Checking Python Version")
        
        version = sys.version_info
        if version.major >= 3 and version.minor >= 9:
            self.print_success(f"Python {version.major}.{version.minor}.{version.micro}")
            return True
        else:
            self.print_error(f"Python 3.9+ required, found {version.major}.{version.minor}")
            return False
    
    def check_env_file(self):
        """Check if .env file exists"""
        self.print_header("Checking Environment Configuration")
        
        env_file = self.project_root / '.env'
        env_example = self.project_root / '.env.example'
        
        if env_file.exists():
            self.print_success(".env file found")
            return True
        elif env_example.exists():
            self.print_error(".env file not found")
            self.print_info("Run: cp .env.example .env")
            self.print_info("Then edit .env with your credentials")
            return False
        else:
            self.print_error("Neither .env nor .env.example found")
            return False
    
    def check_directories(self):
        """Check and create required directories"""
        self.print_header("Checking Directory Structure")
        
        required_dirs = [
            'data/landing',
            'data/raw',
            'logs',
            'airflow/logs',
            'dashboard',
            'config'
        ]
        
        for dir_path in required_dirs:
            full_path = self.project_root / dir_path
            if not full_path.exists():
                full_path.mkdir(parents=True, exist_ok=True)
                self.print_info(f"Created: {dir_path}")
            else:
                self.print_success(f"Exists: {dir_path}")
        
        return True
    
    def check_docker(self):
        """Check if Docker is available"""
        self.print_header("Checking Docker")
        
        try:
            result = subprocess.run(
                ['docker', '--version'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                self.print_success(f"Docker installed: {result.stdout.strip()}")
                return True
        except FileNotFoundError:
            pass
        
        self.print_error("Docker not found")
        self.print_info("Install from: https://www.docker.com/products/docker-desktop")
        return False
    
    def check_postgres(self):
        """Check if PostgreSQL is available"""
        self.print_header("Checking PostgreSQL")
        
        try:
            result = subprocess.run(
                ['psql', '--version'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                self.print_success(f"PostgreSQL installed: {result.stdout.strip()}")
                return True
        except FileNotFoundError:
            pass
        
        self.print_error("PostgreSQL client not found")
        self.print_info("Install from: https://www.postgresql.org/download/")
        return False
    
    def install_dependencies(self):
        """Install Python dependencies"""
        self.print_header("Installing Python Dependencies")
        
        requirements_file = self.project_root / 'requirement.txt'
        
        if not requirements_file.exists():
            self.print_error("requirement.txt not found")
            return False
        
        self.print_info("Installing dependencies... (this may take a few minutes)")
        
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'install', '-r', str(requirements_file)],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                self.print_success("Dependencies installed")
                return True
            else:
                self.print_error(f"Installation failed: {result.stderr}")
                return False
        except Exception as e:
            self.print_error(f"Installation error: {e}")
            return False
    
    def create_dbt_profiles(self):
        """Create DBT profiles file"""
        self.print_header("Checking DBT Configuration")
        
        dbt_dir = Path.home() / '.dbt'
        profiles_file = dbt_dir / 'profiles.yml'
        
        if profiles_file.exists():
            self.print_success("DBT profiles.yml exists")
            return True
        
        dbt_dir.mkdir(exist_ok=True)
        
        profiles_content = """
stat_foot:
  outputs:
    dev:
      type: postgres
      host: localhost
      port: 5432
      user: football_user
      password: your_password_here  # CHANGE THIS
      dbname: football_stats_db
      schema: gold
      threads: 4
  target: dev
"""
        
        profiles_file.write_text(profiles_content)
        self.print_success("Created DBT profiles.yml")
        self.print_info(f"Edit: {profiles_file}")
        return True
    
    def print_summary(self):
        """Print setup summary"""
        self.print_header("Setup Summary")
        
        print(f"\n✅ Passed: {len(self.checks_passed)}")
        print(f"❌ Failed: {len(self.checks_failed)}")
        
        if self.checks_failed:
            print("\nActions required:")
            for check in self.checks_failed:
                print(f"  - {check}")
        
        if not self.checks_failed:
            print("\n🎉 Setup completed successfully!")
            print("\nNext steps:")
            print("  1. Edit .env with your credentials")
            print("  2. Setup PostgreSQL database: make setup-db")
            print("  3. Start Airflow: make start-airflow")
            print("  4. Run extraction: make run-extraction")
            print("  5. Run DBT: make run-dbt")
            print("  6. Launch dashboard: make run-dashboard")
        else:
            print("\n⚠️  Please fix the issues above before proceeding")
    
    def run(self, install_deps=False):
        """Run complete setup"""
        print("\n" + "🚀 " * 15)
        print("  Football ELT Pipeline - Setup Script")
        print("🚀 " * 15)
        
        self.check_python_version()
        self.check_env_file()
        self.check_directories()
        self.check_docker()
        self.check_postgres()
        
        if install_deps:
            self.install_dependencies()
        else:
            self.print_info("\nSkipping dependency installation")
            self.print_info("Run with --install flag to install dependencies")
        
        self.create_dbt_profiles()
        self.print_summary()


if __name__ == "__main__":
    install_deps = '--install' in sys.argv
    
    setup = SetupManager()
    setup.run(install_deps=install_deps)
