
# FreshGrocery

A modern, responsive grocery shopping app. Works on **Windows, macOS, Linux, Android, and iOS** (via browser). Clean design with cart, order history, and admin dashboard.

## Features

- ✨ **Modern responsive design** - Mobile-first, works on all screens
- 🔐 **Secure authentication** - bcrypt password hashing, CSRF protection, rate limiting
- 🛒 **Full shopping cart** - Add/remove items, quantity controls, server-side price validation
- 🧾 **Order history** - Track all your past orders
- 👑 **Admin dashboard** - User management, sales analytics, all order history
- 🔒 **Production-ready** - Configurable for public hosting
- 💾 **Cross-platform** - Runs anywhere Python works

## Admin Credentials

| Username | Password    |
|----------|-------------|
| `groceradmin` | `12345Grocer` |

*Can be overridden via environment variables `ADMIN_USERNAME` and `ADMIN_PASSWORD`*

## Local Development

### Windows

```cmd
cd fresh-grocery
pip install -r requirements.txt
python app.py
```

### macOS/Linux

```bash
cd fresh-grocery
pip install -r requirements.txt
python3 app.py
```

### Android (Termux)

```bash
pkg install python3
pip install -r requirements.txt
python3 app.py
```

Open `http://localhost:5000` in your browser.

## Run with Production Server

### For Linux/macOS (recommended for hosting)

```bash
gunicorn app:app --workers 2 --bind 0.0.0.0:5000
```

### For Windows

```cmd
waitress-serve --host 0.0.0.0 --port 5000 app:app
```

## Environment Variables (for public hosting)

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | Auto-generated | **Required for production** - Strong random key |
| `FORCE_HTTPS` | `0` | Set to `1` if behind HTTPS reverse proxy |
| `DEBUG` | `0` | Set to `1` for debug mode (never in production) |
| `PORT` | `5000` | Port to listen on |
| `HOST` | `0.0.0.0` | Host binding |
| `ADMIN_USERNAME` | `groceradmin` | Admin username |
| `ADMIN_PASSWORD` | `12345Grocer` | Admin password |

## Deployment Options

Free & easy for public hosting:

- [Render](https://render.com/) - Recommended (free tier, HTTPS auto, env vars)
- [Railway](https://railway.app/) - Simple deployment
- [PythonAnywhere](https://www.pythonanywhere.com/) - Great for Python
- [Fly.io](https://fly.io/) - Free allowance

## Security Notes

- Passwords hashed with bcrypt (12 rounds)
- CSRF tokens on all forms
- HttpOnly, SameSite cookies
- Rate limiting on login (5 attempts, 5 min cooldown)
- SQL injection protected (parameterized queries)
- Server-side price validation

## Data Storage

All data is stored in `instance/grocery.db` (SQLite with WAL mode for cross-platform safety). Delete this file to reset everything.
=======
# fresh-grocery
grocery website