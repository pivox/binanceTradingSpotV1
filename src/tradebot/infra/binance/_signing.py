import hashlib
import hmac
import time
from urllib.parse import urlencode


def sign_query(params: dict, secret: str) -> str:
    query = urlencode(params)
    return hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()


def add_auth_params(params: dict, secret: str) -> dict:
    params["timestamp"] = int(time.time() * 1000)
    params["recvWindow"] = 5000
    params["signature"] = sign_query(params, secret)
    return params
