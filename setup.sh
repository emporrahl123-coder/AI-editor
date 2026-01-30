#!/bin/bash

# GitHub AI Editor Setup Script

set -e

echo "🚀 Setting up GitHub AI Editor..."

# Check Python version
python_version=$(python3 --version | cut -d' ' -f2)
required_version="3.9"

if [[ $(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1) != "$required_version" ]]; then
    echo "❌ Python $required_version or higher is required. Found Python $python_version"
    exit 1
fi

echo "✅ Python version: $python_version"

# Check for .env file
if [[ ! -f .env ]]; then
    echo "📝 Creating .env file from template..."
    if [[ -f .env.example ]]; then
        cp .env.example .env
        echo "⚠️ Please edit .env file with your API keys"
    else
        echo "❌ .env.example not found"
        exit 1
    fi
else
    echo "✅ .env file exists"
fi

# Create virtual environment
if [[ ! -d "venv" ]]; then
    echo "🐍 Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "📦 Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p logs temp

# Run tests
echo "🧪 Running tests..."
if python -m pytest tests/ -v; then
    echo "✅ All tests passed"
else
    echo "⚠️ Some tests failed, but continuing setup..."
fi

# Check configuration
echo "🔧 Checking configuration..."
if python config.py; then
    echo "✅ Configuration is valid"
else
    echo "⚠️ Configuration check failed, please review .env file"
fi

echo ""
echo "🎉 Setup complete!"
echo ""
echo "To start the application:"
echo "1. Edit .env file with your API keys"
echo "2. Run: source venv/bin/activate"
echo "3. Run: python app.py"
echo ""
echo "Or using Docker:"
echo "1. Edit .env file"
echo "2. Run: docker-compose up"
echo ""
echo "The web interface will be available at http://localhost:5000"
