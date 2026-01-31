#!/bin/bash

# GitHub AI Editor - Local Development Setup Script
set -e

echo "🚀 Setting up GitHub AI Editor for LOCAL DEVELOPMENT..."

# 1. Check Python
python_version=$(python3 --version | cut -d' ' -f2)
required_version="3.9"
if [[ $(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1) != "$required_version" ]]; then
    echo "❌ Python $required_version or higher is required. Found Python $python_version"
    exit 1
fi
echo "✅ Python version: $python_version"

# 2. Setup environment file
if [[ ! -f .env ]]; then
    echo "📝 Creating .env file from template..."
    if [[ -f .env.example ]]; then
        cp .env.example .env
        echo "⚠️ PLEASE EDIT '.env' FILE WITH YOUR API KEYS NOW"
        echo "   Required keys: GITHUB_TOKEN and OPENAI_API_KEY"
        exit 1  # Stop here so user fills the file
    else
        echo "❌ .env.example not found"
        exit 1
    fi
else
    echo "✅ .env file exists"
fi

# 3. Virtual environment
if [[ ! -d "venv" ]]; then
    echo "🐍 Creating virtual environment..."
    python3 -m venv venv
fi

echo "🔧 Activating virtual environment..."
source venv/bin/activate

# 4. Install dependencies
echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# 5. Install project in editable mode (makes 'src' importable)
echo "📦 Installing project in development mode..."
pip install -e .

# 6. Create directories
echo "📁 Creating directories..."
mkdir -p logs temp

# 7. Quick configuration test
echo "🔧 Testing configuration..."
if python -c "from src.config import config; print('✅ Config import successful')"; then
    echo "✅ Configuration check passed"
else
    echo "❌ Configuration check failed"
    exit 1
fi

echo ""
echo "🎉 LOCAL SETUP COMPLETE!"
echo ""
echo "Next steps:"
echo "1. Edit the '.env' file with your actual API keys"
echo "2. Source the virtual environment: source venv/bin/activate"
echo "3. Run the app locally: python app.py"
echo "4. Open http://localhost:5000 in your browser"
