from __future__ import absolute_import

from .utils import GUID
from . import session

class AuthMixin:
    def get_the_user(self):
        u = None
        s = self.get_secure_cookie('login_session')
        if s:
            u = session.get_data('login_' + s)
        return u

    def set_the_user(self, user):
        self.clear_the_user()
        new_session = GUID.generate()       
        self.set_secure_cookie('login_session', new_session)
        session.set_data('login_' + new_session, user)

    def clear_the_user(self):
        s = self.get_secure_cookie('login_session')
        if s:
            session.clear_data('login_' + s)
        self.clear_cookie('login_session')