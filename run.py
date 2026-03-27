from pathlib import Path

from app import create_app

app = create_app()

if __name__ == "__main__":
    cert_path = Path("certs/server.crt")
    key_path = Path("certs/server.key")

    ssl_context = None
    if cert_path.exists() and key_path.exists():
        ssl_context = (str(cert_path), str(key_path))

    app.run(host="0.0.0.0", port=43255, debug=False, ssl_context=ssl_context)
