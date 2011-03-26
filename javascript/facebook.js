<?depends /javascript/cookie.js?>

var FACEBOOK_APP_ID = <?get facebook_app_id?>

function load_fb()
{
    var fbroot = $('<div id="fb-root"></div>');
    var e = $('<script><' + '/script>'); 
    //e[0].async = true;  -- disabling this because I think at this point we want to load the login stuff ASAP
    e[0].src = document.location.protocol + '//connect.facebook.net/en_US/all.js';
    $(document.body).append(fbroot);
    $(document.body).append(e);
}


/*

This code automates the process of detecting whether the user is logged in, and rendering the page accordingly.

It uses a combination of facebook and a session cookie to decide if the user is logged in.

To use, include this, and define three functions: render_unknown, render_logged_in, render_logged_out.
You can then call do_log_in() and do_log_out().

Here is the sequence of events:

1. Plain HTML loads, is rendered by browser
2. render_unknown is called.  render_unknown should be a lightweight function that displays any placeholder visuals to placate the user while we figure out if they are logged in
3. render_logged_in or render_logged_out is called as soon as we detect the login status.  These functions should call the server and load the appropriate versions of the page
4. ...user uses the page, and calls do_log_in() / do_log_out()...
5. render_logged_in or render_logged_out is called in response to the user's action.  The functions should re-render the page to display it in its new state

*/


//pops up a login box.  if email access is required, pass in the message that should be displayed if email is not present
function do_log_in(callback, email, otherperms)
{
    var p = [];
    if (email) { p.push('email') }
    if (otherperms)
    {
        for (var i = 0; i < otherperms.length; i++) {
            p.push(otherperms[i]);
        }
    }
    $.cookie("fs_session_id", null); //delete the session cookie if present.
    FB.login(function(response) {
        if (response.session) {
            if (email && (!response.perms || $.inArray('email', response.perms.split(',')) == -1))
            {
                displayMessage(email);
                do_log_out(function(){});
            }
            else
            {
                if (callback) {callback(response);}
            }
        }
    }, {perms: p.join(',')});
}

//calls back with true if permission is set, false otherwise
function check_permission(permission, callback)
{
    FB.api({ext_perm: permission, method: 'users.hasAppPermission'}, function(is_set)
    {
        callback(is_set == '1');
    });
}

//if request succeeds, executes callback; if it fails, don't and log it.
function request_permission(permission, callback)
{
    FB.login(function(response) {
        if (!response.perms || $.inArray(permission, response.perms.split(',')) == -1)
        {
            log('not able to request permission ' + permission);
        }
        else
        {
            callback();
        }
    }, {perms: permission});   
}


function do_log_out(callback)
{
    $.cookie("fs_session_id", null); //delete the session cookie if present.
    FB.logout(function(response)
    {
    // user is now logged out -- no code here because we handle this via the event
    });
}

window.fbAsyncInit = function()
{
    FB.init({appId: FACEBOOK_APP_ID, status: true, cookie: true, xfbml: true});
    FB.Event.subscribe('auth.sessionChange', function(response) {
        if (response.session)
        {
            render_logged_in();
        } else
        {
            $.cookie("fs_session_id", null); //delete the session cookie if present.
            render_logged_out();
        }
    });
    
    FB.getLoginStatus(function(response)
    {
        if (response.session)
        {
            render_logged_in();
        }
        else
        {
            $.cookie("fs_session_id", null); //delete the session cookie if present.
            render_logged_out();
        }
    });
};

$(document).ready(function()
{   
    render_unknown();
    
    load_fb();
});