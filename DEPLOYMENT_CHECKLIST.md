# SMART RESTAURANT MANAGEMENT PLATFORM (SRMP)
## Production Deployment Checklist & Pilot Runbook

This checklist serves as the authoritative operational guide for deploying the Smart Restaurant Management Platform into a real-world restaurant pilot.

---

## Phase 1: Pre-Deployment Secrets & Configuration

- [ ] **Generate Production Cryptographic Keys**:
  ```bash
  # Generate 64-character hex secret for JWT signing
  openssl rand -hex 32
  # Generate 64-character hex secret for QR table token signing
  openssl rand -hex 32
  ```
- [ ] **Configure Backend `.env` File**:
  - Set `ENVIRONMENT="production"`
  - Set `SECRET_KEY="<generated-jwt-secret>"`
  - Set `QR_SECRET="<generated-qr-secret>"`
  - Set `DATABASE_URL="postgresql://<user>:<password>@<db-host>:5432/<db-name>"`
  - Set `RAZORPAY_KEY_ID="rzp_live_..."`
  - Set `RAZORPAY_KEY_SECRET="<live-secret>"`
  - Set `BACKEND_CORS_ORIGINS=["https://restaurant.example.com", "https://admin.restaurant.example.com"]`
- [ ] **Configure Frontend `.env` File**:
  - Set `VITE_API_URL="https://api.restaurant.example.com/api/v1"`
  - Set `VITE_WS_URL="wss://api.restaurant.example.com/ws"`
  - Set `VITE_APP_TITLE="Smart Restaurant Management Platform"`

---

## Phase 2: Database Pre-Flight & Migration

- [ ] **Provision Database**:
  - Ensure PostgreSQL 15+ is running with UTF-8 encoding.
  - Verify database connectivity from backend host:
    ```bash
    psql -h <host> -U <user> -d <dbname> -c "SELECT version();"
    ```
- [ ] **Execute Migrations**:
  ```bash
  cd backend
  alembic upgrade head
  ```
- [ ] **Seed Initial Restaurant & Staff Data**:
  ```bash
  python -m app.db.seed
  ```
- [ ] **Verify Default Passwords Changed**:
  - Immediately update default seed passwords for `admin`, `manager`, `chef`, `waiter`, and `cashier` via Admin Dashboard or API.
- [ ] **Create Pre-Launch Backup**:
  ```bash
  python scripts/backup_db.py
  ```

---

## Phase 3: Backend Deployment & Process Supervision

- [ ] **Production Process Manager (Systemd or Docker)**:
  - Configure Gunicorn with Uvicorn worker class:
    ```bash
    gunicorn app.main:app \
      --workers 4 \
      --worker-class uvicorn.workers.UvicornWorker \
      --bind 127.0.0.1:8000 \
      --timeout 120 \
      --keep-alive 5 \
      --access-logfile /var/log/srmp/access.log \
      --error-logfile /var/log/srmp/error.log
    ```
- [ ] **Systemd Service Unit (`/etc/systemd/system/srmp-backend.service`)**:
  - Set `Restart=always`
  - Set `RestartSec=5`
  - Set `LimitNOFILE=65535` for high-volume WebSocket handling.
- [ ] **Health Endpoint Verification**:
  ```bash
  curl -I http://127.0.0.1:8000/health
  # HTTP/1.1 200 OK
  ```

---

## Phase 4: Frontend Compilation & Web Server Proxy

- [ ] **Compile Static Assets**:
  ```bash
  cd frontend
  npm ci
  npm run build
  ```
  - Confirm bundle compiles cleanly with 0 type errors.
- [ ] **Configure Nginx Reverse Proxy with WebSocket Upgrades**:
  ```nginx
  server {
      listen 443 ssl http2;
      server_name restaurant.example.com;

      ssl_certificate /etc/letsencrypt/live/restaurant.example.com/fullchain.pem;
      ssl_certificate_key /etc/letsencrypt/live/restaurant.example.com/privkey.pem;

      # Static Frontend
      location / {
          root /var/www/srmp/frontend/dist;
          try_files $uri $uri/ /index.html;
          expires 7d;
          add_header Cache-Control "public, max-age=604800, immutable";
      }

      # Backend REST APIs
      location /api/ {
          proxy_pass http://127.0.0.1:8000;
          proxy_set_header Host $host;
          proxy_set_header X-Real-IP $remote_addr;
          proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
          proxy_set_header X-Forwarded-Proto $scheme;
      }

      # Real-time WebSocket Upgrades
      location /ws/ {
          proxy_pass http://127.0.0.1:8000;
          proxy_http_version 1.1;
          proxy_set_header Upgrade $http_upgrade;
          proxy_set_header Connection "Upgrade";
          proxy_set_header Host $host;
          proxy_read_timeout 3600s;
          proxy_send_timeout 3600s;
      }
  }
  ```

---

## Phase 5: Hardware & Physical Restaurant Setup

- [ ] **Restaurant Wi-Fi Segregation**:
  - **SSID 1 (Customer Wi-Fi)**: Captive portal or open QR dining Wi-Fi.
  - **SSID 2 (Staff Wi-Fi)**: WPA3 secured internal network for Kitchen Tablets, Waiter Handhelds, and Cashier POS.
- [ ] **Table QR Code Stands**:
  - Print physical QR codes using the generated table token URLs (`https://restaurant.example.com/menu?table=X&token=Y`).
  - Verify physical scan redirects to correct table context on both iOS Camera and Android Lens.
- [ ] **Kitchen Display Tablets (KDS)**:
  - Mount 10-inch or larger Android/iPad tablets in the kitchen.
  - Enable "Kiosk Mode" or "Pinned App" in browser at `/kitchen`.
  - Disable screen auto-lock / sleep mode.
- [ ] **Thermal Receipt Printers (Optional)**:
  - Test ESC/POS or browser print dialog for bill receipts at `/billing`.

---

## Phase 6: Post-Deployment Smoke Verification

- [ ] **Test Staff Login**: Login as Admin, Manager, Cashier, Waiter, Chef.
- [ ] **Test QR Code Scan**: Open table QR, verify table number is locked.
- [ ] **Test Customer Order Flow**: Add items, apply customization, place order.
- [ ] **Verify Real-Time KDS Progression**: Order appears in kitchen without page reload, move to Preparing, then Ready.
- [ ] **Verify Waiter Notification**: Order Ready alert received on Waiter screen.
- [ ] **Test Digital Bill & Razorpay Payment**: Settle bill via Razorpay Sandbox/Live, verify table moves to Cleaning.
- [ ] **Test Offline Bill Payment**: Verify Cashier settles offline cash payment.
- [ ] **Verify Live Analytics**: Admin dashboard displays updated Revenue, Order Count, and Average Order Value.

---

## Phase 7: Emergency Rollback & Recovery Protocol

In the event of an unexpected critical incident during pilot operations:

1. **Revert Application Binary / Code**:
   ```bash
   git checkout <last-known-good-commit>
   npm run build # if frontend
   sudo systemctl restart srmp-backend
   ```
2. **Restore Database from Snapshot**:
   ```bash
   python scripts/restore_db.py backups/smart_restaurant_backup_<TIMESTAMP>.db
   sudo systemctl restart srmp-backend
   ```
3. **Fallback to Paper / Offline Operations**:
   - Cashiers can record orders directly via POS or physical order slips while the database is restored.
   - All historical bills remain intact in the pre-restore snapshot.

