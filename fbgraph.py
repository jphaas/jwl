import deployconfig
import facebook
import web

def getFBUser(exception = True):
    """Returns the user.  If exception = True (the default), raises an exception if not found"""
    user = facebook.get_user_from_cookie(web.cookies(), deployconfig.get('facebook_app_id'), deployconfig.get('facebook_app_secret'))
    if user is None and exception:
        raise Exception('could not connect to facebook, please try again')
    return user
    
    