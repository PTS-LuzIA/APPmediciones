#!/bin/bash

# =====================================================
# APPmediciones - Start Script
# =====================================================

echo "=========================================="
echo "🚀 Starting APPmediciones"
echo "=========================================="

# Colores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Directorio del script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Crear directorio de logs si no existe
mkdir -p logs

# Verificar PostgreSQL
echo -e "\n${YELLOW}Checking PostgreSQL...${NC}"
if ! pg_isready -h localhost -p 5432 > /dev/null 2>&1; then
    echo -e "${RED}❌ PostgreSQL is not running on port 5432${NC}"
    echo -e "${YELLOW}Starting PostgreSQL...${NC}"

    # Intentar iniciar PostgreSQL (ajustar según sistema)
    if command -v brew &> /dev/null; then
        # macOS con Homebrew
        brew services start postgresql@14 2>/dev/null || brew services start postgresql 2>/dev/null
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
    echo -e "${YELLOW}⚠ No virtual environment found (using system Python)${NC}"
fi

# Verificar que los puertos estén libres antes de iniciar
echo -e "\n${YELLOW}Checking ports...${NC}"

if lsof -ti:8005 >/dev/null 2>&1; then
    echo -e "${YELLOW}Port 8005 in use, stopping existing process...${NC}"
    lsof -ti:8005 | xargs kill -9 2>/dev/null
    sleep 2
fi

if lsof -ti:3016 >/dev/null 2>&1; then
    echo -e "${YELLOW}Port 3016 in use, stopping existing process...${NC}"
    lsof -ti:3016 | xargs kill -9 2>/dev/null
    sleep 2
fi

# Iniciar Backend
echo -e "\n${YELLOW}Starting Backend API (port 8005)...${NC}"
cd "$SCRIPT_DIR/backend"

# Iniciar backend en background
nohup python main.py > "$SCRIPT_DIR/logs/backend.log" 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > "$SCRIPT_DIR/logs/backend.pid"

# Esperar a que el backend esté listo
echo -e "Waiting for backend to start..."
for i in {1..10}; do
    if lsof -ti:8005 >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

if lsof -ti:8005 >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Backend started (PID: $BACKEND_PID)${NC}"
else
    echo -e "${RED}❌ Failed to start backend${NC}"
    echo -e "${YELLOW}Last 20 lines of backend.log:${NC}"
    tail -20 "$SCRIPT_DIR/logs/backend.log"
    exit 1
fi

cd "$SCRIPT_DIR"

# Iniciar Frontend
echo -e "\n${YELLOW}Starting Frontend (port 3016)...${NC}"
cd "$SCRIPT_DIR/frontend"

# Verificar si node_modules existe, si no, instalar dependencias
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}Installing frontend dependencies...${NC}"
    npm install
    echo -e "${GREEN}✓ Dependencies installed${NC}"
fi

# Iniciar frontend en background
nohup npm run dev > "$SCRIPT_DIR/logs/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > "$SCRIPT_DIR/logs/frontend.pid"

# Esperar a que el frontend esté listo
echo -e "Waiting for frontend to start..."
for i in {1..15}; do
    if lsof -ti:3016 >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

if lsof -ti:3016 >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Frontend started (PID: $FRONTEND_PID)${NC}"
else
    echo -e "${RED}❌ Failed to start frontend${NC}"
    echo -e "${YELLOW}Last 20 lines of frontend.log:${NC}"
    tail -20 "$SCRIPT_DIR/logs/frontend.log"
    exit 1
fi

cd "$SCRIPT_DIR"

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
