from flask import Flask, render_template
import os

from flask_injector import FlaskInjector

template_dir = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


FlaskInjector(app=app)


if __name__ == "__main__":
    app.run()
