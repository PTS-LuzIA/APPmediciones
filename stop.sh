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

# Detener Backend
if [ -f "logs/backend.pid" ]; then
    BACKEND_PID=$(cat logs/backend.pid)
    echo -e "\n${YELLOW}Stopping Backend (PID: $BACKEND_PID)...${NC}"

    if ps -p $BACKEND_PID > /dev/null 2>&1; then
        kill $BACKEND_PID
        sleep 2

        # Forzar si todavía está corriendo
        if ps -p $BACKEND_PID > /dev/null 2>&1; then
            echo -e "${YELLOW}Force killing backend...${NC}"
            kill -9 $BACKEND_PID
        fi

        echo -e "${GREEN}✓ Backend stopped${NC}"
    else
        echo -e "${YELLOW}Backend process not running${NC}"
    fi

    rm -f logs/backend.pid
else
    echo -e "${YELLOW}No backend PID file found${NC}"

    # Intentar matar por puerto
    BACKEND_PIDS=$(lsof -ti:8005)
    if [ ! -z "$BACKEND_PIDS" ]; then
        echo -e "${YELLOW}Found process on port 8005, stopping...${NC}"
        kill $BACKEND_PIDS 2>/dev/null || kill -9 $BACKEND_PIDS 2>/dev/null
        echo -e "${GREEN}✓ Process on port 8005 stopped${NC}"
    fi
fi

# Detener Frontend (cuando esté disponible)
if [ -f "logs/frontend.pid" ]; then
    FRONTEND_PID=$(cat logs/frontend.pid)
    echo -e "\n${YELLOW}Stopping Frontend (PID: $FRONTEND_PID)...${NC}"

    if ps -p $FRONTEND_PID > /dev/null 2>&1; then
        kill $FRONTEND_PID
        sleep 2

        # Forzar si todavía está corriendo
        if ps -p $FRONTEND_PID > /dev/null 2>&1; then
            echo -e "${YELLOW}Force killing frontend...${NC}"
            kill -9 $FRONTEND_PID
        fi

        echo -e "${GREEN}✓ Frontend stopped${NC}"
    else
        echo -e "${YELLOW}Frontend process not running${NC}"
    fi

    rm -f logs/frontend.pid
else
    # Intentar matar por puerto
    FRONTEND_PIDS=$(lsof -ti:3016)
    if [ ! -z "$FRONTEND_PIDS" ]; then
        echo -e "${YELLOW}Found process on port 3016, stopping...${NC}"
        kill $FRONTEND_PIDS 2>/dev/null || kill -9 $FRONTEND_PIDS 2>/dev/null
        echo -e "${GREEN}✓ Process on port 3016 stopped${NC}"
    fi
fi

# Verificar que los puertos estén libres
echo -e "\n${YELLOW}Verifying ports...${NC}"

if lsof -Pi :8005 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo -e "${RED}❌ Port 8005 still in use${NC}"
else
    echo -e "${GREEN}✓ Port 8005 is free${NC}"
fi

if lsof -Pi :3016 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo -e "${RED}❌ Port 3016 still in use${NC}"
else
    echo -e "${GREEN}✓ Port 3016 is free${NC}"
fi

echo ""
echo "=========================================="
echo -e "${GREEN}✓ APPmediciones Stopped${NC}"
echo "=========================================="
echo ""
echo "Note: PostgreSQL is still running"
echo "To stop PostgreSQL:"
echo "  macOS: brew services stop postgresql"
echo "  Linux: sudo systemctl stop postgresql"
echo "=========================================="
