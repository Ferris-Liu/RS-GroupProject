import os
from flask import Flask
from dotenv import load_dotenv

load_dotenv()

def create_app():
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static"
    )
    app.secret_key = os.urandom(24)

    from . import routes
    app.register_blueprint(routes.bp)

    return app
