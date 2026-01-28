#!/bin/bash

# =====================================================
# APPmediciones - Start Script
# =====================================================

set -e

echo "=========================================="
echo "🚀 Starting APPmediciones"
echo "=========================================="

# Colores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Verificar PostgreSQL
echo -e "\n${YELLOW}Checking PostgreSQL...${NC}"
if ! pg_isready -h localhost -p 5432 > /dev/null 2>&1; then
    echo -e "${RED}❌ PostgreSQL is not running on port 5432${NC}"
    echo -e "${YELLOW}Starting PostgreSQL...${NC}"

    # Intentar iniciar PostgreSQL (ajustar según sistema)
    if command -v brew &> /dev/null; then
        # macOS con Homebrew
        brew services start postgresql@14 || brew services start postgresql
    elif command -v systemctl &> /dev/null; then
        # Linux con systemd
        sudo systemctl start postgresql
    else
        echo -e "${RED}Please start PostgreSQL manually${NC}"
        exit 1
    fi

    # Esperar a que PostgreSQL esté listo
    sleep 3
fi

if pg_isready -h localhost -p 5432 > /dev/null 2>&1; then
    echo -e "${GREEN}✓ PostgreSQL is running${NC}"
else
    echo -e "${RED}❌ Failed to start PostgreSQL${NC}"
    exit 1
fi

# Crear base de datos si no existe
echo -e "\n${YELLOW}Checking database...${NC}"
if ! psql -lqt | cut -d \| -f 1 | grep -qw appmediciones_db; then
    echo -e "${YELLOW}Creating database appmediciones_db...${NC}"
    createdb appmediciones_db
    echo -e "${GREEN}✓ Database created${NC}"
else
    echo -e "${GREEN}✓ Database exists${NC}"
fi

# Activar entorno virtual Python si existe
if [ -d "venv" ]; then
    echo -e "\n${YELLOW}Activating Python virtual environment...${NC}"
    source venv/bin/activate
    echo -e "${GREEN}✓ Virtual environment activated${NC}"
elif [ -d ".venv" ]; then
    echo -e "\n${YELLOW}Activating Python virtual environment...${NC}"
    source .venv/bin/activate
    echo -e "${GREEN}✓ Virtual environment activated${NC}"
else
    echo -e "${YELLOW}⚠ No virtual environment found (venv or .venv)${NC}"
fi

# Instalar dependencias si es necesario
if [ -f "backend/requirements.txt" ]; then
    echo -e "\n${YELLOW}Checking Python dependencies...${NC}"
    pip install -q -r backend/requirements.txt
    echo -e "${GREEN}✓ Dependencies installed${NC}"
fi

# Iniciar Backend
echo -e "\n${YELLOW}Starting Backend API (port 8005)...${NC}"
cd backend

# Verificar si ya hay un proceso corriendo en el puerto 8005
if lsof -Pi :8005 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo -e "${RED}❌ Port 8005 is already in use${NC}"
    echo -e "${YELLOW}Run ./stop.sh first to stop existing services${NC}"
    exit 1
fi

# Iniciar backend en background
nohup python main.py > ../logs/backend.log 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > ../logs/backend.pid

# Esperar a que el backend esté listo
sleep 3

if ps -p $BACKEND_PID > /dev/null; then
    echo -e "${GREEN}✓ Backend started (PID: $BACKEND_PID)${NC}"
else
    echo -e "${RED}❌ Failed to start backend${NC}"
    cat ../logs/backend.log
    exit 1
fi

cd ..

# Iniciar Frontend
echo -e "\n${YELLOW}Starting Frontend (port 3016)...${NC}"
cd frontend

# Verificar si ya hay un proceso corriendo en el puerto 3016
if lsof -Pi :3016 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo -e "${RED}❌ Port 3016 is already in use${NC}"
    echo -e "${YELLOW}Run ./stop.sh first to stop existing services${NC}"
    exit 1
fi

# Verificar si node_modules existe, si no, instalar dependencias
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}Installing frontend dependencies...${NC}"
    npm install
    echo -e "${GREEN}✓ Dependencies installed${NC}"
fi

# Iniciar frontend en background
nohup npm run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > ../logs/frontend.pid

# Esperar a que el frontend esté listo
sleep 5

if ps -p $FRONTEND_PID > /dev/null; then
    echo -e "${GREEN}✓ Frontend started (PID: $FRONTEND_PID)${NC}"
else
    echo -e "${RED}❌ Failed to start frontend${NC}"
    cat ../logs/frontend.log | tail -20
    exit 1
fi

cd ..

echo ""
echo "=========================================="
echo -e "${GREEN}✓ APPmediciones Started Successfully${NC}"
echo "=========================================="
echo ""
echo "Services:"
echo "  🔹 Frontend:    http://localhost:3016"
echo "  🔹 Backend API: http://localhost:8005"
echo "  🔹 API Docs:    http://localhost:8005/docs"
echo "  🔹 Database:    postgresql://localhost:5432/appmediciones_db"
echo ""
echo "Logs:"
echo "  📄 Frontend:    tail -f logs/frontend.log"
echo "  📄 Backend:     tail -f logs/backend.log"
echo ""
echo "To stop: ./stop.sh"
echo "=========================================="
