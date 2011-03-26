import deployconfig
import facebook

def getFBUser(exception = False):
    """Returns the user.  If exception = True (the default), raises an exception if not found"""
    user = facebook.get_user_from_cookie(web.cookies(), deployconfig.get('facebook_app_id'), deployconfig.get('facebook_app_secret'))
    if user is None and exception:
        raise Exception(exception)
    return user
    
    