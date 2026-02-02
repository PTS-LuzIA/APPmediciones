#!/bin/bash

# =====================================================
# APPmediciones - Stop Script
# =====================================================

echo "=========================================="
echo "🛑 Stopping APPmediciones"
echo "=========================================="

# Colores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Función para matar procesos en un puerto
kill_port() {
    local PORT=$1
    local PIDS=$(lsof -ti:$PORT 2>/dev/null)

    if [ ! -z "$PIDS" ]; then
        echo -e "${YELLOW}Killing processes on port $PORT: $PIDS${NC}"
        echo $PIDS | xargs kill -9 2>/dev/null
        sleep 1
        return 0
    fi
    return 1
}

# Detener Backend
echo -e "\n${YELLOW}Stopping Backend...${NC}"

# 1. Matar por PID file si existe
if [ -f "logs/backend.pid" ]; then
    BACKEND_PID=$(cat logs/backend.pid)
    if ps -p $BACKEND_PID > /dev/null 2>&1; then
        echo -e "Killing backend PID: $BACKEND_PID"
        kill -9 $BACKEND_PID 2>/dev/null
    fi
    rm -f logs/backend.pid
fi

# 2. Matar por puerto 8005
kill_port 8005

# 3. Matar procesos python main.py en el directorio backend
pkill -9 -f "python.*main.py" 2>/dev/null

# 4. Matar procesos uvicorn en puerto 8005
pkill -9 -f "uvicorn.*8005" 2>/dev/null

sleep 2

# Verificar que el puerto 8005 esté libre
if lsof -ti:8005 >/dev/null 2>&1; then
    echo -e "${YELLOW}Port 8005 still occupied, force killing...${NC}"
    lsof -ti:8005 | xargs kill -9 2>/dev/null
    sleep 1
fi

if ! lsof -ti:8005 >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Backend stopped (port 8005 free)${NC}"
else
    echo -e "${RED}❌ Could not free port 8005${NC}"
fi

# Detener Frontend
echo -e "\n${YELLOW}Stopping Frontend...${NC}"

# 1. Matar por PID file si existe
if [ -f "logs/frontend.pid" ]; then
    FRONTEND_PID=$(cat logs/frontend.pid)
    if ps -p $FRONTEND_PID > /dev/null 2>&1; then
        echo -e "Killing frontend PID: $FRONTEND_PID"
        kill -9 $FRONTEND_PID 2>/dev/null
    fi
    rm -f logs/frontend.pid
fi

# 2. Matar por puerto 3016
kill_port 3016

# 3. Matar procesos next-server
pkill -9 -f "next-server" 2>/dev/null
pkill -9 -f "next dev" 2>/dev/null
pkill -9 -f "npm.*dev.*3016" 2>/dev/null

sleep 2

# Verificar que el puerto 3016 esté libre
if lsof -ti:3016 >/dev/null 2>&1; then
    echo -e "${YELLOW}Port 3016 still occupied, force killing...${NC}"
    lsof -ti:3016 | xargs kill -9 2>/dev/null
    sleep 1
fi

if ! lsof -ti:3016 >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Frontend stopped (port 3016 free)${NC}"
else
    echo -e "${RED}❌ Could not free port 3016${NC}"
fi

# Verificación final
echo -e "\n${YELLOW}Final verification...${NC}"

BACKEND_OK=true
FRONTEND_OK=true

if lsof -ti:8005 >/dev/null 2>&1; then
    echo -e "${RED}❌ Port 8005 still in use${NC}"
    BACKEND_OK=false
else
    echo -e "${GREEN}✓ Port 8005 is free${NC}"
fi

if lsof -ti:3016 >/dev/null 2>&1; then
    echo -e "${RED}❌ Port 3016 still in use${NC}"
    FRONTEND_OK=false
else
    echo -e "${GREEN}✓ Port 3016 is free${NC}"
fi

echo ""
echo "=========================================="
if [ "$BACKEND_OK" = true ] && [ "$FRONTEND_OK" = true ]; then
    echo -e "${GREEN}✓ APPmediciones Stopped Successfully${NC}"
else
    echo -e "${YELLOW}⚠ Some processes may still be running${NC}"
    echo -e "Try: lsof -i :8005 and lsof -i :3016"
fi
echo "=========================================="
echo ""
echo "Note: PostgreSQL is still running"
echo "To stop PostgreSQL:"
echo "  macOS: brew services stop postgresql"
echo "  Linux: sudo systemctl stop postgresql"
echo "=========================================="
