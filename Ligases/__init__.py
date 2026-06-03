from flask import Blueprint

ligases_bp = Blueprint('ligases', __name__, url_prefix='/api/ligases')

from . import routes  # import the endpoints

from .routes import ligases_bp
