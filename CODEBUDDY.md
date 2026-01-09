# CODEBUDDY.md

This file provides guidance to CodeBuddy Code when working with code in this repository.

## Project Overview

AsterDEX Multi-Wallet Management System is a Flask-based web application for managing multiple cryptocurrency trading wallets and executing automated trading strategies on the AsterDEX exchange. The system supports both spot and futures trading, with multi-process strategy execution, real-time monitoring, and secure API key storage.

## Core Architecture

### MVC Pattern
- **Models** (`models/`): SQLAlchemy ORM models for database entities (User, Wallet, Task, Strategy, SystemConfig)
- **Controllers** (`controllers/`): Flask blueprints handling HTTP requests and business logic routing
- **Services** (`services/`): Business logic layer (AuthService, WalletService, TaskService, StrategyService)

### Key Components

**App Factory Pattern** (`app.py`):
- `create_app()` function initializes the Flask application
- Automatically creates database tables, default admin user, and default strategies on startup
- Cleans up orphan processes on startup to prevent zombie tasks

**Task Execution Architecture**:
- Tasks run in independent processes via `task_runner.py`
- Each task gets its own Python process with isolated execution
- Process management handled by `ProcessManager` utility (`utils/process_manager.py`)
- Task logs written to `task_logs/` directory, one file per task

**Trading Clients**:
- `spot_client.py` - AsterDEX spot trading API client with HMAC SHA256 signing
- `futures_client.py` - AsterDEX futures trading API client with Ethereum wallet signing
- `simple_trading_client.py` - Simplified spot client for volume strategy
- `market_trading_client.py` - Market order client

**Strategy System**:
- Strategies defined in `strategies/` directory
- Each strategy is a class with `connect()`, `run()`, and `set_logger()` methods
- Strategy metadata stored in database `strategies` table (module path, class name, parameters)
- Current strategies:
  - `VolumeStrategy` - Spot volume washing strategy (buy/sell same quantity at same price)
  - `HiddenFuturesStrategy` - Futures hidden order self-trading strategy

**Security**:
- API keys encrypted at rest using Fernet symmetric encryption (`utils/encryption.py`)
- Encryption key configured in `ENCRYPTION_KEY` environment variable (must be 32 chars)
- Wallet credentials auto-encrypted/decrypted via Wallet model methods
- Authentication via Flask-Login with role-based access control (admin users)

**Proxy Support**:
- Two-tier proxy system:
  1. Global proxy (development): SOCKS5 proxy configured in `.env` for all requests
  2. Task-level proxy (production): Smartproxy residential IP assigned per task
- Proxy configuration via `utils/smartproxy_manager.py` and `utils/proxy_config.py`
- Smartproxy enabled/disabled via database config or environment variable

## Common Development Commands

### Running the Application
```bash
# Start the Flask application
python app.py

# Run a specific task directly (for debugging)
python task_runner.py <task_id>

# Run a standalone strategy
cd strategies
python volume_strategy.py
```

### Environment Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Activate virtual environment (Windows)
.venv\Scripts\activate

# Activate virtual environment (Linux/Mac)
source .venv/bin/activate
```

### Database Operations
```bash
# Initialize database with schema
python -c "from app import create_app; app = create_app(); app.app_context().push(); from models.base import db; db.create_all()"

# Check configuration status
python config_env.py
```

### Testing Trading Clients
```bash
# Check wallet balances
python check_wallets.py
```

## Configuration

### Environment Variables (`.env`)
Essential configuration files:
- `.env` - Base configuration (development)
- `.envProd` - Production overrides
- `.env.local` - Local development overrides (highest priority)

Key environment variables:
```
# Database (Required)
DB_HOST=localhost
DB_PORT=3306
DB_USERNAME=root
DB_PASSWORD=<your_password>
DB_DATABASE=aster_auto

# Flask (Required)
FLASK_SECRET_KEY=<your-secret-key>
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=true

# Security (Required - must be 32 chars)
ENCRYPTION_KEY=<32-character-key>

# Proxy (Development)
PROXY_ENABLED=true
PROXY_HOST=127.0.0.1
PROXY_PORT=7890
PROXY_TYPE=socks5

# Smartproxy (Production)
SMARTPROXY_ENABLED=true
SMARTPROXY_BASE_USERNAME=<username>
SMARTPROXY_PASSWORD=<password>
SMARTPROXY_RESIDENTIAL_HOST=gate.decodo.com
SMARTPROXY_RESIDENTIAL_PORT=10001
SMARTPROXY_SESSION_DURATION=60
```

### Database Configuration
- MySQL database with InnoDB engine
- Tables: users, wallets, tasks, strategies, system_config
- ORM: Flask-SQLAlchemy with PyMySQL driver
- Schema file: `aster_auto.sql` (reference only, app creates tables automatically)

## Important Implementation Details

### Task Lifecycle
1. User creates task via web UI → TaskService validates and saves to database
2. TaskService.start_task() uses ProcessManager to spawn `task_runner.py` process
3. `task_runner.py` loads task, wallet, strategy, and credentials from database
4. Strategy connects to exchange API using wallet credentials (decrypted)
5. Strategy runs in loop for specified rounds with interval between rounds
6. Progress/stats updated in Task model after each round
7. On completion/failure, task status updated and process terminated

### Multi-Wallet System
- Users can have multiple wallets (spot or futures type)
- Each wallet stores encrypted API credentials in database
- Wallet credentials never exposed in environment variables (security best practice)
- Task-runner decrypts credentials at runtime per task
- Support for both API key auth (spot) and wallet signing (futures with private keys)

### Strategy Development
To add a new strategy:
1. Create strategy class in `strategies/<strategy_name>.py`
2. Implement required methods:
   - `__init__(self, symbol, quantity, ...)` - Initialize with parameters
   - `connect()` - Initialize trading client and verify connection
   - `set_logger(logger)` - Set logging instance for the strategy
   - `run()` - Execute the strategy, return True on success, False on failure
3. Add strategy record to `strategies` table via database or StrategyService
4. Set `module_path` to `strategies.<strategy_name>` and `class_name` to class name
5. Wallet model will auto-encrypt/decrypt credentials for strategy use

### Proxy Configuration Priority
1. Database config `smartproxy_enabled` (highest priority)
2. Environment variable `SMARTPROXY_ENABLED` (fallback)
3. Task-specific proxy assigned via Smartproxy manager (production)
4. Global SOCKS5 proxy (development fallback)

### Logging
- Task logs: `task_logs/<task_name>.log` (one file per task, unique by task name)
- System logs: `logs/` directory (if configured)
- Task progress parsed in real-time via `utils/task_progress_parser.py`
- Log format: `YYYY-MM-DD HH:MM:SS - LEVEL - message`

### Default Admin Account
- Username: `admin`
- Password: `admin123`
- Created automatically on first run if not exists
- Can view/manage all wallets and tasks across all users

### API Client Architecture
- All API clients support proxy configuration
- Spot client uses HMAC SHA256 signature with timestamp
- Futures client uses Ethereum wallet signing (web3.py)
- Clients handle server time synchronization automatically
- Retry logic and error handling built-in

### Task Statistics Tracking
Tasks track comprehensive statistics:
- `completed_rounds`, `failed_rounds`, `total_rounds`
- `supplement_orders` - Additional orders placed for recovery
- `buy_volume_usdt`, `sell_volume_usdt` - Trading volume
- `total_fees_usdt` - Total trading fees paid
- `initial_usdt_balance`, `final_usdt_balance`, `usdt_balance_diff` - Balance tracking
- `net_loss_usdt` - Net loss after accounting for fees
- Statistics updated in real-time during strategy execution

### Orphan Process Cleanup
- App startup checks for tasks marked as "running" in database
- Verifies if process actually exists using psutil
- Cleans up orphaned tasks (updates status to 'stopped')
- Prevents zombie processes from accumulating

## Troubleshooting

### Task Not Starting
1. Check task logs in `task_logs/<task_name>.log`
2. Verify wallet credentials are correctly encrypted/decrypted
3. Test proxy connectivity if enabled
4. Check API credentials are valid and have sufficient balance

### Database Connection Issues
- Ensure MySQL service is running
- Verify DB_HOST, DB_PORT, DB_USERNAME, DB_PASSWORD in `.env`
- Check database `aster_auto` exists
- Verify user has proper permissions

### Proxy Issues
- For development: Ensure local SOCKS5 proxy is running (default: 127.0.0.1:7890)
- For production: Check Smartproxy credentials are valid
- Test proxy connectivity via `utils/tests/proxy_connection_test.py`

### Encryption Key Issues
- ENCRYPTION_KEY must be exactly 32 characters
- Changing key will make existing encrypted data unreadable
- Backup database before changing encryption key

## File Structure Summary
```
app.py                      # Flask app factory and entry point
task_runner.py              # Task execution in separate process
config_env.py               # Environment configuration loader
spot_client.py              # AsterDEX spot trading client
futures_client.py           # AsterDEX futures trading client
simple_trading_client.py    # Simplified trading client
market_trading_client.py    # Market order client
check_wallets.py            # Wallet balance checker utility

models/                     # SQLAlchemy ORM models
  - base.py                 # Database base configuration
  - user.py                 # User model (authentication, roles)
  - wallet.py               # Wallet model (API credentials, encrypted)
  - task.py                 # Task model (trading tasks, statistics)
  - strategy.py             # Strategy model (strategy metadata)
  - system_config.py        # System configuration model

services/                   # Business logic layer
  - auth_service.py         # User authentication and authorization
  - wallet_service.py       # Wallet CRUD operations
  - task_service.py         # Task lifecycle management
  - strategy_service.py     # Strategy management

controllers/                # Flask blueprints (API routes)
  - main_controller.py      # Dashboard, main pages
  - auth_controller.py      # Login/logout routes
  - wallet_controller.py    # Wallet management UI
  - task_controller.py      # Task management UI

strategies/                 # Trading strategy implementations
  - volume_strategy.py      # Spot volume washing strategy
  - hidden_futures_strategy.py  # Futures hidden order strategy

utils/                      # Utility functions
  - encryption.py           # Data encryption/decryption
  - process_manager.py      # Process spawn/terminate
  - task_logger.py          # Task log file management
  - proxy_config.py         # Proxy configuration
  - smartproxy_manager.py   # Smartproxy IP assignment
  - task_progress_parser.py # Parse task progress from logs

routes/                     # Additional route modules
  - auth.py                 # Authentication routes
  - users.py                # User management routes (new)
  - config.py               # System configuration routes

templates/                  # Jinja2 HTML templates
task_logs/                  # Task execution logs (generated at runtime)
```
