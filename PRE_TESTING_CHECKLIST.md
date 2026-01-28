# Pre-Testing Checklist

Before starting to test APPmediciones, verify that everything is set up correctly.

## ✅ Environment Setup

### PostgreSQL Database

- [ ] PostgreSQL 15+ is installed and running
  ```bash
  psql --version
  # Should show: psql (PostgreSQL) 15.x or higher
  ```

- [ ] Database `appmediciones_db` exists
  ```bash
  psql -U postgres -l | grep appmediciones
  # Should show: appmediciones_db
  ```

- [ ] Schema and tables created
  ```bash
  psql -U postgres -d appmediciones_db -c "\dt appmediciones.*"
  # Should show 5 tables: conceptos, mediciones, nodos, proyectos, usuarios
  ```

- [ ] Admin user exists
  ```bash
  psql -U postgres -d appmediciones_db -c "SELECT username, email, es_admin FROM appmediciones.usuarios WHERE username='admin';"
  # Should show: admin | admin@appmediciones.local | t
  ```

**If any check fails:**
```bash
# Create database
psql -U postgres -c "CREATE DATABASE appmediciones_db;"

# Run migrations
cd /Volumes/DATOS_IA/G_Drive_LuzIA/IA/Proyectos/MVP/APPmediciones
psql -U postgres -d appmediciones_db -f backend/database/migrations/001_initial_schema.sql
```

---

## ✅ Python Environment

### Backend Directory

- [ ] Navigate to backend directory
  ```bash
  cd /Volumes/DATOS_IA/G_Drive_LuzIA/IA/Proyectos/MVP/APPmediciones/backend
  ```

- [ ] Virtual environment exists
  ```bash
  ls -la venv/
  # Should show venv directory
  ```

- [ ] Virtual environment activated
  ```bash
  which python
  # Should show path containing "venv"
  ```

- [ ] Dependencies installed
  ```bash
  pip list | grep fastapi
  # Should show: fastapi 0.115.12 or similar
  ```

**If any check fails:**
```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate  # Mac/Linux
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

---

## ✅ Backend Server

### Start the Server

- [ ] Server starts without errors
  ```bash
  cd /Volumes/DATOS_IA/G_Drive_LuzIA/IA/Proyectos/MVP/APPmediciones/backend
  source venv/bin/activate
  python main.py
  ```

**Expected output:**
```
============================================================
🚀 APPmediciones API v1.0.0
   Entorno: development
   Puerto: 8001
   Database: localhost:5432/appmediciones_db
============================================================
✓ Conexión a base de datos OK
INFO:     Uvicorn running on http://0.0.0.0:8001 (Press CTRL+C to quit)
INFO:     Started reloader process [XXXX] using StatReload
INFO:     Started server process [XXXX]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

**If you see errors:**

1. **Database connection error:**
   - Check PostgreSQL is running: `psql -U postgres -l`
   - Check DATABASE_URL in `.env` or `config.py`
   - Verify database exists and migrations were run

2. **Import errors:**
   - Check venv is activated
   - Reinstall dependencies: `pip install -r requirements.txt`

3. **Port already in use:**
   - Kill existing process: `lsof -ti:8001 | xargs kill -9`
   - Or change port in `config.py`

---

## ✅ API Endpoints

### Health Check

- [ ] Health endpoint works
  ```bash
  curl http://localhost:8001/health
  ```

**Expected response:**
```json
{"status":"healthy","version":"1.0.0","environment":"development"}
```

### Swagger UI

- [ ] Open Swagger UI in browser: http://localhost:8001/docs

- [ ] You should see 5 sections:
  - **Authentication** (4 endpoints)
  - **Proyectos** (7 endpoints)
  - **Nodos** (6 endpoints)
  - **Conceptos** (6 endpoints)
  - **Procesamiento** (4 endpoints)

- [ ] Total: **35 endpoints** displayed

### ReDoc

- [ ] Open ReDoc: http://localhost:8001/redoc
- [ ] Documentation loads correctly

---

## ✅ Authentication Test

### Login with Admin

- [ ] Go to Swagger UI: http://localhost:8001/docs

- [ ] Expand `POST /api/auth/login`

- [ ] Click "Try it out"

- [ ] Enter credentials:
  ```json
  {
    "username": "admin",
    "password": "admin123"
  }
  ```

- [ ] Click "Execute"

- [ ] Response status: **200 OK**

- [ ] Response body contains:
  ```json
  {
    "access_token": "eyJhbGciOiJIUz...",
    "token_type": "bearer",
    "user": {
      "id": 1,
      "username": "admin",
      "email": "admin@appmediciones.local",
      "es_admin": true,
      "activo": true
    }
  }
  ```

- [ ] Copy the `access_token` value

### Authorize in Swagger

- [ ] Click **"Authorize"** button (🔒) at the top of Swagger UI

- [ ] Paste: `Bearer <your-access-token>`
  - Example: `Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`
  - **Important**: Include the word "Bearer" followed by a space

- [ ] Click "Authorize"

- [ ] Click "Close"

- [ ] Padlock icons (🔒) should now show as locked

---

## ✅ Quick Functionality Test

### Test 1: Create a Project

- [ ] Expand `POST /api/proyectos`
- [ ] Click "Try it out"
- [ ] Enter:
  ```json
  {
    "nombre": "Test Project",
    "descripcion": "Quick test"
  }
  ```
- [ ] Click "Execute"
- [ ] Response status: **201 Created**
- [ ] **Note the project `id`** from response (e.g., 1)

### Test 2: List Projects

- [ ] Expand `GET /api/proyectos`
- [ ] Click "Try it out" → "Execute"
- [ ] Response status: **200 OK**
- [ ] You should see your created project in the list

### Test 3: Get Project Details

- [ ] Expand `GET /api/proyectos/{id}`
- [ ] Enter the project ID from Test 1
- [ ] Click "Execute"
- [ ] Response status: **200 OK**
- [ ] Response contains project with statistics

---

## ✅ File Structure Verification

- [ ] All files exist:
  ```bash
  cd /Volumes/DATOS_IA/G_Drive_LuzIA/IA/Proyectos/MVP/APPmediciones

  # Check key files
  ls -la backend/main.py
  ls -la backend/config.py
  ls -la backend/requirements.txt
  ls -la backend/api/routes/auth.py
  ls -la backend/api/routes/proyectos.py
  ls -la backend/api/routes/nodos.py
  ls -la backend/api/routes/conceptos.py
  ls -la backend/api/routes/procesamiento.py
  ls -la backend/database/manager.py
  ls -la backend/models/proyecto.py
  ls -la docs/API.md
  ls -la docs/TESTING.md
  ls -la IMPLEMENTATION_SUMMARY.md
  ```

- [ ] Directories exist:
  ```bash
  ls -la backend/api/
  ls -la backend/api/routes/
  ls -la backend/api/schemas/
  ls -la backend/models/
  ls -la backend/database/
  ls -la backend/services/
  ls -la backend/parsers/
  ls -la backend/utils/
  ls -la docs/
  ls -la logs/
  ls -la uploads/
  ```

---

## ✅ Documentation Verification

- [ ] All documentation files exist and are readable:
  ```bash
  cat README.md | head -20
  cat QUICKSTART.md | head -20
  cat IMPLEMENTATION_SUMMARY.md | head -20
  cat docs/ARQUITECTURA.md | head -20
  cat docs/API.md | head -20
  cat docs/TESTING.md | head -20
  cat STATUS.md | head -20
  ```

---

## 🎯 Final Checklist Summary

Before proceeding to full testing, ensure ALL of these are checked:

**Environment:**
- [ ] PostgreSQL running
- [ ] Database created with migrations
- [ ] Admin user exists
- [ ] Python venv created and activated
- [ ] Dependencies installed

**Server:**
- [ ] Backend starts without errors
- [ ] Server listening on port 8001
- [ ] Database connection successful
- [ ] No error messages in console

**API:**
- [ ] Health endpoint responds
- [ ] Swagger UI loads
- [ ] 35 endpoints visible
- [ ] Login works
- [ ] Authorization works
- [ ] Can create project
- [ ] Can list projects
- [ ] Can get project details

**Documentation:**
- [ ] All documentation files present
- [ ] Can read and understand docs
- [ ] TESTING.md provides clear instructions

---

## 🚀 Ready to Test!

If **ALL** checks above are ✅, you're ready to proceed with comprehensive testing.

**Next steps:**

1. **Read** [docs/TESTING.md](docs/TESTING.md) for detailed test scenarios
2. **Follow** test scenarios 1-6 step by step
3. **Test** with a real PDF if available
4. **Report** any bugs or issues found

---

## 🆘 If Something Doesn't Work

### Quick Troubleshooting

1. **Check backend logs:**
   ```bash
   tail -f logs/backend.log
   ```

2. **Check database:**
   ```bash
   psql -U postgres -d appmediciones_db
   \dt appmediciones.*
   SELECT * FROM appmediciones.usuarios;
   \q
   ```

3. **Restart server:**
   ```bash
   # Press Ctrl+C to stop
   # Then restart:
   python main.py
   ```

4. **Regenerate token:**
   - Login again via `/api/auth/login`
   - Copy new token
   - Re-authorize in Swagger

5. **Check port:**
   ```bash
   lsof -i :8001
   # If something else is using port 8001, kill it or change port in config.py
   ```

### Common Issues

| Issue | Solution |
|-------|----------|
| Database connection failed | Check PostgreSQL running, database exists, migrations run |
| Module not found | Activate venv, reinstall dependencies |
| Port already in use | Kill process on port 8001 or change port |
| 401 Unauthorized | Login again, get new token, re-authorize |
| 403 Forbidden | Check you're owner of resource or admin |
| 404 Not Found | Check resource exists, verify ID is correct |

---

## 📞 Support Resources

- [QUICKSTART.md](QUICKSTART.md) - Setup instructions
- [docs/API.md](docs/API.md) - API reference
- [docs/TESTING.md](docs/TESTING.md) - Testing guide
- [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) - What's implemented

Interactive docs:
- http://localhost:8001/docs (Swagger UI)
- http://localhost:8001/redoc (ReDoc)

---

**Good luck with testing! 🎉**
