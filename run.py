import os

from app import create_app

app = create_app()


if __name__ == "__main__":
    if app.config["DEBUG"]:
        app.run(debug=True)
    else:
        from waitress import serve

        serve(app, host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
