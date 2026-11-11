# Smart Restaurant Management Platform (SRMP)
### Enterprise Multi-Portal Hospitality Ecosystem

A unified, real-time restaurant management platform connecting **Customers**, **Kitchen Staff**, **Waiters**, and **Restaurant Administrators** through a single high-performance system.

Built from scratch using:
- **Frontend**: React 19, TypeScript, Vite, Tailwind CSS, Lucide Icons, Recharts, React Router
- **Backend**: Python 3.12, FastAPI, WebSockets, SQLAlchemy 2.0 ORM, Pydantic v2
- **Database**: PostgreSQL (Production) / SQLite (Local Fast-Boot), Alembic Migrations
- **Payment Gateway**: Razorpay (Sandbox & Production Webhooks)
- **Security**: JWT Authentication, Role-Based Access Control (RBAC), Cryptographic HMAC Table QR Tokens

---

## 🏛️ System Architecture

```mermaid
flowchart TD
    subgraph Clients["Frontend Applications (React + TypeScript)"]
        CustApp["📱 Customer App\n• QR Code Table Access\n• Digital Menu & Dietary Badges\n• Cart & Order Placement\n• Live Order Tracking\n• Call Waiter & Wi-Fi\n• Bill Split & Razorpay"]
        KDSApp["🍳 Kitchen Display System\n• Live Kanban Display\n• Elapsed Prep Timers\n• Delayed Order Warnings\n• 1-Click Status Progression\n• Real-Time Audio Alerts"]
        StaffApp["🤵 Staff / Waiter Portal\n• Real-Time Floor Map\n• Service Request Queue\n• Table Status Toggling\n• Shift & Role Context"]
        AdminApp["📊 Restaurant Administration\n• Live Operational KPIs\n• Recharts Sales Analytics\n• Full Menu CRUD & Customizations\n• Table & QR Code Generator\n• Reservation Management\n• Billing & Tax Settings"]
    end

    subgraph BackendGateway["Central Backend (FastAPI + Python 3.12)"]
        APIGateway["REST API Endpoints\n/api/v1/*"]
        WSManager["WebSocket Connection Manager\n• /ws/kitchen\n• /ws/staff\n• /ws/admin\n• /ws/table/{id}"]
        Security["Security Layer\n• JWT Bearer Auth\n• RBAC Engine\n• HMAC QR Signer"]
    end

    subgraph DataStorage["Persistence & External Services"]
        DB[("PostgreSQL / SQLite\n11 Relational Tables\nForeign Keys & Indexes")]
        Alembic["Alembic Migrations"]
        Razorpay["💳 Razorpay Payment Gateway\n(Sandbox / Webhook)"]
    end

    CustApp <-->|"HTTP / REST"| APIGateway
    CustApp <-->|"WebSocket Events"| WSManager
    KDSApp <-->|"HTTP / REST"| APIGateway
    KDSApp <-->|"WebSocket Events"| WSManager
    StaffApp <-->|"HTTP / REST"| APIGateway
    StaffApp <-->|"WebSocket Events"| WSManager
    AdminApp <-->|"HTTP / REST"| APIGateway
    AdminApp <-->|"WebSocket Events"| WSManager

    APIGateway --> Security
    APIGateway --> DB
    Security --> DB
    WSManager -.->|"Broadcast Events"| Clients
    APIGateway <-->|"Orders & Verification"| Razorpay
    Alembic --> DB
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- **Node.js** (v18+)
- **Python** (v3.10+)

### 2. Backend Setup
```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Seed initial data (automatic on first run, or run manually)
python -m app.utils.seed_data

# Start FastAPI server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
API Documentation will be live at: `http://localhost:8000/docs`

### 3. Frontend Setup
```bash
cd frontend

# Install npm dependencies
npm install

# Start Vite development server
npm run dev
```
Frontend will be accessible at: `http://localhost:5173`

---

## 🔑 Development Seeding & Production Provisioning

- **Development / Local Demo (`ENVIRONMENT=development`)**: `python -m app.utils.seed_data` populates the sample *Royal Saffron* tenant without hardcoded passwords in application source. Passwords are read from `SUPERADMIN_INITIAL_PASSWORD` and `SEED_DEMO_*_PASSWORD` environment variables (or generated randomly per run with `must_change_password=true`).
- **Production (`ENVIRONMENT=production`)**: Demo seeding (`SEED_DEMO_DATA=true`) is disabled and rejected at startup; known demo fixture passwords and `@royalsaffron.com` fixture emails are blocked from authentication. Onboard real restaurant owners via `/register` or `/api/v1/onboarding/register`, and provision the platform super-admin with a strong random `SUPERADMIN_INITIAL_PASSWORD`.

| Role | Username | Access Rights |
|------|----------|---------------|
| **Platform Super Admin** | `superadmin` | Multi-tenant governance, platform subscriptions, billing overview |
| **Admin** | `admin` *(dev seed)* | Full administrative control, analytics, menu CRUD, settings |
| **Manager** | `manager` *(dev seed)* | Operations, table assignments, floor, reservations, menu |
| **Waiter** | `waiter` *(dev seed)* | Floor map, service requests, order assistance, bill delivery |
| **Kitchen** | `chef` *(dev seed)* | Kitchen Display System, preparation timers, status updates |
| **Cashier** | `cashier` *(dev seed)* | Billing settlements, cash/card payment records, receipts |

---

## 📱 Portals & Application Routes

- `/table/:qrToken` - **Customer Application** (Mobile-first QR dining experience)
- `/table/:qrToken/cart` - **Shopping Cart & Checkout**
- `/table/:qrToken/track/:orderId` - **Live Order Tracker**
- `/table/:qrToken/wifi` - **Guest Wi-Fi Connection Information**
- `/table/:qrToken/split-bill` - **Bill Splitting & Tip Calculator**
- `/table/:qrToken/service` - **Call Waiter & Service Requests**
- `/table/:qrToken/reserve` - **Table Reservation Request**
- `/kitchen` - **Kitchen Display System (KDS)**
- `/staff` - **Staff & Waiter Portal**
- `/admin` - **Restaurant Administration Hub**
  - `/admin/overview` - Dynamic Operational KPIs
  - `/admin/analytics` - Sales Trends & Category Charts
  - `/admin/menu` - Menu & Customizations Manager
  - `/admin/tables` - Floor Map & Table QR Generator
  - `/admin/staff` - Staff RBAC Management
  - `/admin/reservations` - Reservation Queue & Table Allocations
  - `/admin/billing` - Invoices, Taxes & Settlement Logs
  - `/admin/settings` - Restaurant Profile, Wi-Fi & GST Settings
- `/login` - **Staff Authentication Gateway**
- `/pricing`, `/terms`, `/privacy`, `/refund`, `/contact` - **Public Compliance & Transparent Pricing Pages**

---

## 💳 SaaS Subscription Pricing & Individual Business Operating Model

- **Operating Model:** `INDIVIDUAL_UNREGISTERED` (platform operated by an individual owner under the SRMP brand/trade name; legal owner name, bank reference, GST status, domain, and contact channels are environment-configurable and marked pending until verified).
- **Direct Tax-Inclusive Pricing:**
  - **Monthly Plan:** **₹999/month** (`99,900` integer paise) — inclusive of applicable taxes and compulsory charges.
  - **Yearly Plan:** **₹9,999/year** (`999,900` integer paise) — inclusive of applicable taxes and compulsory charges.
- **Tax Treatment:** While operating as an unregistered individual business (`IS_GST_REGISTERED=false`), GST is not collected and Non-GST Payment Receipts (`R{FY}/...`) are issued. If GST registration + CA confirmation are enabled in configuration (`IS_GST_REGISTERED=true`, `IS_GST_RATE_CA_CONFIRMED=true`), 18% GST is extracted inclusively (`84,661 + 15,239 = 99,900` monthly; `847,373 + 152,527 = 999,900` yearly) without ever increasing the advertised final price.
- **Dual-Flow Settlement Isolation:** Flow A restaurant customer dining payments settle strictly to each restaurant's own Razorpay merchant account; Flow B SaaS subscriptions settle strictly to the platform owner's configured merchant bank account. Live-mode payment flags remain disabled (`false`) by default for safe test-mode development.
