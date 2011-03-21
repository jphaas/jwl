#monkey patch disabling curl's CA authentication
from .. import deployconfig
if deployconfig.get('debug'):
    # from tornado.curl_httpclient import CurlAsyncHTTPClient
    # def new_create(max_simultaneous_connections=None):
        # c = self._curl_create(max_simultaneous_connections)
        # c.setopt(pycurl.SSL_VERIFYPEER, 0)
        # return c
    # CurlAsyncHTTPClient._curl_create = new_create
    from tornado.httpclient import HTTPRequest
    
    old_init = HTTPRequest.__init__
    
    def new_init(self, url, method="GET", headers=None, body=None,
                 auth_username=None, auth_password=None,
                 connect_timeout=20.0, request_timeout=20.0,
                 if_modified_since=None, follow_redirects=True,
                 max_redirects=5, user_agent=None, use_gzip=True,
                 network_interface=None, streaming_callback=None,
                 header_callback=None, prepare_curl_callback=None,
                 proxy_host=None, proxy_port=None, proxy_username=None,
                 proxy_password='', allow_nonstandard_methods=False,
                 validate_cert=False, ca_certs=None):
        return old_init(self, url, method, headers, body,
                 auth_username, auth_password,
                 connect_timeout, request_timeout,
                 if_modified_since, follow_redirects,
                 max_redirects, user_agent, use_gzip,
                 network_interface, streaming_callback,
                 header_callback, prepare_curl_callback,
                 proxy_host, proxy_port, proxy_username,
                 proxy_password, allow_nonstandard_methods,
                 validate_cert, ca_certs)
    
    HTTPRequest.__init__ = new_init