import random
import sha
import smtplib
import sys
import time
import urllib
import base64
import hmac
import imaplib

class struct:
    pass

def do_it(email, consumer_key, consumer_secret, access_key, access_secret):
    consumer = struct()
    consumer.key = consumer_key
    consumer.secret = consumer_secret
    access = struct()
    access.key = access_key
    access.secret = access_secret
    xoauth_string = GenerateXOauthString(consumer, access, email, 'imap', None, None, None)
    return TestImapAuthentication('imap.googlemail.com', email, xoauth_string)
    
def UrlEscape(text):
  # See OAUTH 5.1 for a definition of which characters need to be escaped.
  return urllib.quote(text, safe='~-._')


def UrlUnescape(text):
  # See OAUTH 5.1 for a definition of which characters need to be escaped.
  return urllib.unquote(text)


def FormatUrlParams(params):
  """Formats parameters into a URL query string.

  Args:
    params: A key-value map.

  Returns:
    A URL query string version of the given parameters.
  """
  param_fragments = []
  for param in sorted(params.iteritems(), key=lambda x: x[0]):
    param_fragments.append('%s=%s' % (param[0], UrlEscape(param[1])))
  return '&'.join(param_fragments)


def EscapeAndJoin(elems):
  return '&'.join([UrlEscape(x) for x in elems])


def GenerateSignatureBaseString(method, request_url_base, params):
  """Generates an OAuth signature base string.

  Args:
    method: The HTTP request method, e.g. "GET".
    request_url_base: The base of the requested URL. For example, if the
      requested URL is
      "https://mail.google.com/mail/b/xxx@googlemail.com/imap/?" +
      "xoauth_requestor_id=xxx@googlemail.com", the request_url_base would be
      "https://mail.google.com/mail/b/xxx@googlemail.com/imap/".
    params: Key-value map of OAuth parameters, plus any parameters from the
      request URL.

  Returns:
    A signature base string prepared according to the OAuth Spec.
  """
  return EscapeAndJoin([method, request_url_base, FormatUrlParams(params)])


def GenerateHmacSha1Signature(text, key):
  digest = hmac.new(key, text, sha)
  return base64.b64encode(digest.digest())


def GenerateOauthSignature(base_string, consumer_secret, token_secret):
  key = EscapeAndJoin([consumer_secret, token_secret])
  return GenerateHmacSha1Signature(base_string, key)

def TestImapAuthentication(imap_hostname, user, xoauth_string):
  """Authenticates to IMAP with the given xoauth_string.

  Prints a debug trace of the attempted IMAP connection.

  Args:
    imap_hostname: Hostname or IP address of the IMAP service.
    user: The Google Mail username (full email address)
    xoauth_string: A valid XOAUTH string, as returned by GenerateXOauthString.
        Must not be base64-encoded, since IMAPLIB does its own base64-encoding.
  """
  imap_conn = imaplib.IMAP4_SSL(imap_hostname)
  imap_conn.debug = 4
  imap_conn.authenticate('XOAUTH', lambda x: xoauth_string)
  return imap_conn.list()
  #imap_conn.select('INBOX')
  
def FillInCommonOauthParams(params, consumer, nonce=None, timestamp=None):
  """Fills in parameters that are common to all oauth requests.

  Args:
    params: Parameter map, which will be added to.
    consumer: An OAuthEntity representing the OAuth consumer.
    nonce: optional supplied nonce
    timestamp: optional supplied timestamp
  """
  params['oauth_consumer_key'] = consumer.key
  if nonce:
    params['oauth_nonce'] = nonce
  else:
    params['oauth_nonce'] = str(random.randrange(2**64 - 1))
  params['oauth_signature_method'] = 'HMAC-SHA1'
  params['oauth_version'] = '1.0'
  if timestamp:
    params['oauth_timestamp'] = timestamp
  else:
    params['oauth_timestamp'] = str(int(time.time()))
  
def GenerateXOauthString(consumer, access_token, user, proto,
                         xoauth_requestor_id, nonce, timestamp):
  """Generates an IMAP XOAUTH authentication string.

  Args:
    consumer: An OAuthEntity representing the consumer.
    access_token: An OAuthEntity representing the access token.
    user: The Google Mail username (full email address)
    proto: "imap" or "smtp", for example.
    xoauth_requestor_id: xoauth_requestor_id URL parameter for 2-legged OAuth
    nonce: optional supplied nonce
    timestamp: optional supplied timestamp

  Returns:
    A string that can be passed as the argument to an IMAP
    "AUTHENTICATE XOAUTH" command after being base64-encoded.
  """
  method = 'GET'
  url_params = {}
  if xoauth_requestor_id:
    url_params['xoauth_requestor_id'] = xoauth_requestor_id
  oauth_params = {}
  FillInCommonOauthParams(oauth_params, consumer, nonce, timestamp)
  if access_token.key:
    oauth_params['oauth_token'] = access_token.key
  signed_params = oauth_params.copy()
  signed_params.update(url_params)
  request_url_base = (
      'https://mail.google.com/mail/b/%s/%s/' % (user, proto))
  base_string = GenerateSignatureBaseString(
      method,
      request_url_base,
      signed_params)
  print 'signature base string:\n' + base_string + '\n'
  signature = GenerateOauthSignature(base_string, consumer.secret,
                                     access_token.secret)
  oauth_params['oauth_signature'] = signature

  formatted_params = []
  for k, v in sorted(oauth_params.iteritems()):
    formatted_params.append('%s="%s"' % (k, UrlEscape(v)))
  param_list = ','.join(formatted_params)
  if url_params:
    request_url = '%s?%s' % (request_url_base,
                             FormatUrlParams(url_params))
  else:
    request_url = request_url_base
  preencoded = '%s %s %s' % (method, request_url, param_list)
  print 'xoauth string (before base64-encoding):\n' + preencoded + '\n'
  return preencoded
