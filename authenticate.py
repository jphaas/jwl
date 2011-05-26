from __future__ import absolute_import

from .utils import GUID
from . import session
import time

EXPIRED = -2

class AuthMixin:
    def get_the_user(self):
        """Returns EXPIRED if expired or None if not found"""
        s = self.get_secure_cookie('login_session')
        if s:
            exp = session.get_data('expiration_' + s)
            if exp and time.time() > exp:
                return EXPIRED
            return session.get_data('login_' + s)
        return None

    def set_the_user(self, user, expires):
        self.clear_the_user()
        new_session = GUID.generate()       
        self.set_secure_cookie('login_session', new_session, expires_days = None if expires else 365)
        session.set_data('login_' + new_session, user)
        session.set_data('expiration_' + new_session, time.time() + 60 * 60 * 24 if expires else None)

    def clear_the_user(self):
        s = self.get_secure_cookie('login_session')
        if s:
            session.clear_data('login_' + s)
            session.clear_data('expiration_' + s)
        self.clear_cookie('login_session')