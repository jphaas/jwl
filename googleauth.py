from __future__ import absolute_import
import tornado.web
from tornado.auth import GoogleMixin
from urlparse import urlparse, urlunparse

from . import session

from .authenticate import AuthMixin

scopes = {
    'gmail': 'https://mail.google.com/',
    'contacts': 'http://www.google.com/m8/feeds/',
    'calendar': 'http://www.google.com/calendar/feeds/'
}

class LoginController(tornado.web.RequestHandler, AuthMixin, GoogleMixin):
    @tornado.web.asynchronous
    def get(self, command):
        if command == 'login':
            print 'in login'
            self.authenticate_redirect(callback_uri = self._switch_command('login_callback'), ax_attrs=["name","email"])
        elif command == 'authorize':
            print 'in authorize'
            scope_list = ' '.join([scopes[p] for p in self.request.arguments['perms']])
            self.authorize_redirect(scope_list, callback_uri=self._switch_command('auth_callback'), ax_attrs=["name","email"])
        elif command == "login_callback":
            print 'in login_callback'
            self.get_authenticated_user(self.async_callback(self._on_login))
        elif command == 'auth_callback':
            print 'in auth callback'
            self.get_authenticated_user(self.async_callback(self._on_auth))
        elif command == 'logout':
            print 'in logout'
            self.clear_the_user()
            self.redirect('/')
        else:
            raise Exception('unrecognized command ' + command)
            
    def _on_login(self, user):
        print 'in on login'
        if user:
            self.set_the_user(user['email'])
        self.redirect('/')
        
    def _on_auth(self, user):
        print 'in on auth'
        if user:
            self.set_the_user(user['email'])
            session.set_data('usertoken_' + user['email'], user['access_token'])
        self.redirect('/')
    
    def _switch_command(self, newcommand):
        parsed = list(urlparse(self.request.uri))
        split = parsed[2].split('/')
        split[-1] = newcommand
        parsed[2] = '/'.join(split)
        return urlunparse(parsed)