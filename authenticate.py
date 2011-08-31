from __future__ import absolute_import

from .utils import GUID
from . import session
import time

class NotLoggedInException(Exception): pass

class AuthMixin:
    def get_the_user(self):
        """Returns None if not found"""
        if hasattr(self, '_user_set_on_this_request'):
            return self._user_set_on_this_request
        s = self.get_secure_cookie('login_session')
        clear = True
        try:
            if not s: return None
            user = session.get_data('login_' + s)
            if not user: return None
            # if session.get_data('user_' + user) != s: return None #Make sure only one session per user is valid at any given time
            exp = session.get_data('expiration_' + s)
            if exp and time.time() > exp:
                return None
            clear = False    
            return user
        finally:
            if clear: self.clear_cookie('login_session')

    def set_the_user(self, user, expires):
        self.clear_the_user()
        self._user_set_on_this_request = user
        new_session = GUID.generate()       
        self.set_secure_cookie('login_session', new_session, expires_days = None if expires else 365)
        session.set_data('login_' + new_session, user)
        session.set_data('expiration_' + new_session, time.time() + 60 * 60 * 24 if expires else None)
        # session.set_data('user_' + user, new_session) #Make sure only one session per user is valid at any given time

    def clear_the_user(self):
        if hasattr(self, '_user_set_on_this_request'): del self._user_set_on_this_request
        user = self.get_the_user()
#         if user:
#             session.clear_data('user_' + user)
#         s = self.get_secure_cookie('login_session')
#         if s:
#             session.clear_data('login_' + s)
#             session.clear_data('expiration_' + s)
        self.clear_cookie('login_session')
