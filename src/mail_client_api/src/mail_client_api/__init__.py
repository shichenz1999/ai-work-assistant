"""Public export surface for ``mail_client_api``."""

from mail_client_api import message
from mail_client_api.client import Client, get_client, get_client_for_user
from mail_client_api.message import Message, get_message

__all__ = ["Client", "Message", "get_client", "get_client_for_user", "get_message", "message"]
