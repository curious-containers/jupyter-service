import os

from flask import Flask, render_template
import cc_jupyter_service.service.db as db

DESCRIPTION = 'CC-Agency Broker.'


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='dev',  # TODO: overwrite dev
        DATABASE=os.path.join(app.instance_path, 'flaskr.sqlite'),
    )

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    @app.route('/', methods=['GET'])
    def get_root():
        return render_template('hello.html')

    db.init_app(app)

    return app
