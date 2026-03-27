from flask import Blueprint

from ..core import API_PREFIX


api_bp = Blueprint("api", __name__, url_prefix=API_PREFIX)


from . import admin, auth, bills, groups, profile  # noqa: E402,F401
