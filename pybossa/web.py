# -*- coding: utf8 -*-
# This file is part of PyBossa.
#
# Copyright (C) 2013 SF Isle of Man Limited
#
# PyBossa is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# PyBossa is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with PyBossa.  If not, see <http://www.gnu.org/licenses/>.

import os
import logging
import json
import os
# FC addon
import urllib2
import json

from flask import Response, request, g, render_template,\
        abort, flash, redirect, session, url_for
from flask.ext.login import login_user, logout_user, current_user
from flask.ext.babel import lazy_gettext
from sqlalchemy.exc import UnboundExecutionError
from sqlalchemy import func, desc
from werkzeug.exceptions import *

import pybossa
from pybossa.core import app, login_manager, db, babel
import pybossa.model as model
from pybossa.api import blueprint as api
from pybossa.view.account import blueprint as account
from pybossa.view.applications import blueprint as applications
from pybossa.view.admin import blueprint as admin
from pybossa.view.leaderboard import blueprint as leaderboard
from pybossa.view.stats import blueprint as stats
from pybossa.view.help import blueprint as help
from pybossa.cache import apps as cached_apps
from pybossa.cache import users as cached_users
from pybossa.cache import categories as cached_cat
from pybossa.ratelimit import get_view_rate_limit

##unosat addon
from pybossa.model import User
from sqlalchemy.sql import text

logger = logging.getLogger('pybossa')

# other views ...
app.register_blueprint(api, url_prefix='/api')
app.register_blueprint(account, url_prefix='/account')
app.register_blueprint(applications, url_prefix='/app')
app.register_blueprint(admin, url_prefix='/admin')
app.register_blueprint(leaderboard, url_prefix='/leaderboard')
app.register_blueprint(stats, url_prefix='/stats')
app.register_blueprint(help, url_prefix='/help')

# Enable Twitter if available
try:
    if (app.config['TWITTER_CONSUMER_KEY'] and
            app.config['TWITTER_CONSUMER_SECRET']):
        from pybossa.view.twitter import blueprint as twitter
        app.register_blueprint(twitter, url_prefix='/twitter')
except Exception as inst:
    print type(inst)
    print inst.args
    print inst
    print "Twitter singin disabled"

# Enable Facebook if available
try:
    if (app.config['FACEBOOK_APP_ID'] and app.config['FACEBOOK_APP_SECRET']):
        from pybossa.view.facebook import blueprint as facebook
        app.register_blueprint(facebook, url_prefix='/facebook')
except Exception as inst:
    print type(inst)
    print inst.args
    print inst
    print "Facebook singin disabled"

# Enable Google if available
try:
    if (app.config['GOOGLE_CLIENT_ID'] and app.config['GOOGLE_CLIENT_SECRET']):
        from pybossa.view.google import blueprint as google
        app.register_blueprint(google, url_prefix='/google')
except Exception as inst:
    print type(inst)
    print inst.args
    print inst
    print "Google singin disabled"

# Check if app stats page can generate the map
geolite = app.root_path + '/../dat/GeoLiteCity.dat'
if not os.path.exists(geolite):
    app.config['GEO'] = False
    print("GeoLiteCity.dat file not found")
    print("App page stats web map disabled")
else:
    app.config['GEO'] = True


def url_for_other_page(page):
    args = request.view_args.copy()
    args['page'] = page
    return url_for(request.endpoint, **args)
app.jinja_env.globals['url_for_other_page'] = url_for_other_page


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500


@app.errorhandler(403)
def forbidden(e):
    return render_template('403.html'), 403


@app.errorhandler(401)
def unauthorized(e):
    return render_template('401.html'), 401


@app.after_request
def inject_x_rate_headers(response):
    limit = get_view_rate_limit()
    if limit and limit.send_x_headers:
        h = response.headers
        h.add('X-RateLimit-Remaining', str(limit.remaining))
        h.add('X-RateLimit-Limit', str(limit.limit))
        h.add('X-RateLimit-Reset', str(limit.reset))
    return response

@app.context_processor
def global_template_context():
    if current_user.is_authenticated():
        if (current_user.email_addr == current_user.name or
                current_user.email_addr == "None"):
            flash(lazy_gettext("Please update your e-mail address in your profile page,"
                  " right now it is empty!"), 'error')

    # Cookies warning
    cookie_name = app.config['BRAND'] + "_accept_cookies"
    show_cookies_warning = False
    print request.cookies.get(cookie_name)
    if not request.cookies.get(cookie_name):
        show_cookies_warning = True

    # Announcement sections
    if app.config.get('ANNOUNCEMENT'):
        announcement = app.config['ANNOUNCEMENT']
        if current_user.is_authenticated():
            for key in announcement.keys():
                if key == 'admin' and current_user.admin:
                    flash(announcement[key], 'info')
                if key == 'owner' and len(current_user.apps) != 0:
                    flash(announcement[key], 'info')
                if key == 'user':
                    flash(announcement[key], 'info')

    if app.config.get('CONTACT_EMAIL'):
        contact_email = app.config.get('CONTACT_EMAIL')
    else:
        contact_email = 'info@pybossa.com'

    if app.config.get('CONTACT_TWITTER'):
        contact_twitter = app.config.get('CONTACT_TWITTER')
    else:
        contact_twitter = 'PyBossa'

    return dict(
        brand=app.config['BRAND'],
        title=app.config['TITLE'],
        logo=app.config['LOGO'],
        copyright=app.config['COPYRIGHT'],
        description=app.config['DESCRIPTION'],
        terms_of_use=app.config['TERMSOFUSE'],
        data_use=app.config['DATAUSE'],
        enforce_privacy=app.config['ENFORCE_PRIVACY'],
        version=pybossa.__version__,
        current_user=current_user,
        show_cookies_warning=show_cookies_warning,
        contact_email=contact_email,
        contact_twitter=contact_twitter)


@login_manager.user_loader
def load_user(username):
    return db.session.query(model.User).filter_by(name=username).first()


@app.before_request
def api_authentication():
    """ Attempt API authentication on a per-request basis."""
    apikey = request.args.get('api_key', None)
    from flask import _request_ctx_stack
    if 'Authorization' in request.headers:
        apikey = request.headers.get('Authorization')
    if apikey:
        user = db.session.query(model.User).filter_by(api_key=apikey).first()
        ## HACK:
        # login_user sets a session cookie which we really don't want.
        # login_user(user)
        if user:
            _request_ctx_stack.top.user = user

@app.route('/survey_check_complete')
def survey_check_complete():
    """ Records completion of taking surveys"""
    if current_user.is_authenticated() and current_user.survey_check == "YES":
        current_user.survey_check = "COMPLETE"
        db.session.commit()
    return redirect(url_for('home')) 

@app.route('/survey_check_yes')
def survey_check_yes():
    """ Records user's opinion to  keep taking surveys"""
    if current_user.is_authenticated():
        current_user.survey_check = "YES"
        db.session.commit()
    return redirect(url_for('home')) 

@app.route('/survey_check_no')
def survey_check_no():
    """ Records user's opinion to not keep taking surveys"""
    if current_user.is_authenticated():
        current_user.survey_check = "NO"
        db.session.commit()
    return redirect(url_for('home'))    

"""
DEBUG CODE
"""
@app.route('/survey_check_none')
def survey_check_none():
    """ Records user's opinion to not keep taking surveys"""
    if current_user.is_authenticated():
        current_user.survey_check = "None"
        db.session.commit()
    return redirect(url_for('home'))   

@app.route('/survey_check')
def survey_check():
    """ Check Survey requirements for geotagx """
    d = {}
    print current_user
    if current_user.is_authenticated() and current_user.survey_check != "NO" :
        return render_template('/survey_check/survey_check.html', **d)
    else:
        return redirect(url_for('home'))

@app.route('/')
def home():
    """ Render home page with the cached apps and users"""
    d = {'featured': cached_apps.get_featured_front_page(),
         'top_apps': cached_apps.get_top(),
         'top_users': None,
         'categories': None,
         'apps': None,
         'n_apps_per_category': None}

    if app.config['ENFORCE_PRIVACY'] and current_user.is_authenticated():
        if current_user.admin:
            d['top_users'] = cached_users.get_top()
    if not app.config['ENFORCE_PRIVACY']:
        d['top_users'] = cached_users.get_top()
    # @FC
    categories = cached_cat.get_all()
    n_apps_per_category = dict()
    apps = dict()
    for c in categories:
        n_apps_per_category[c.short_name] = cached_apps.n_count(c.short_name)
        apps[c.short_name],count = cached_apps.get(c.short_name,1,1)
    d['categories'] = categories
    d['n_apps_per_category'] = n_apps_per_category
    d['apps'] = apps
    # Current user Survey System
    print current_user
    if current_user.is_authenticated():
        # Check if survey_check is None
        # That is the case of a first time registration
        if current_user.survey_check == "None" :
            return redirect(url_for('survey_check'))
        if current_user.survey_check == "YES" :
            sql = text('''SELECT COUNT(task_run.id) AS task_run FROM task_run WHERE :cur_user_id=task_run.user_id''')
            results = db.engine.execute(sql,cur_user_id=current_user.id)
            num_run_task = 0
            for row in results:
                num_run_task = row.task_run
            print "Number of tasks run : ",num_run_task
            if num_run_task > 5:
                return render_template('/survey_check/survey_check_complete.html', **d)

	# @FC
    return render_template('/home/index.html', **d)


@app.route("/about")
def about():
    """Render the about template"""
    return render_template("/home/about.html")

@app.route("/find_photos")
def find_photos():
    """Render the about template"""
    return render_template("/home/find_photos.html")
	
@app.route("/analyse_photos")
def analyse_photos():
    """Render the about template"""
    return render_template("/home/analyse_photos.html")


@app.route("/get_flickr_gallery")
def get_flickr_gallery():
    #d = {'gallery_url': request.args.get('gallery_url', None) }
    #d = {'gallery_url': "a"}
    gallery_url=request.args.get('gallery_url', None)
    response = urllib2.urlopen('https://api.flickr.com/services/rest/?method=flickr.urls.lookupGallery&api_key=440a683988a7da58f576256cb68bc270&url='+gallery_url+'&format=json&nojsoncallback=1')
    data = json.load(response)  
    gallery_id=data['gallery']['id']
    #print data
    response2 = urllib2.urlopen('https://api.flickr.com/services/rest/?method=flickr.galleries.getPhotos&api_key=440a683988a7da58f576256cb68bc270&gallery_id='+gallery_id+'&format=json&nojsoncallback=1')
    photo_data = json.load(response2)
    #return json.dumps(photo_data)
    #https://farm{farm-id}.staticflickr.com/{server-id}/{id}_{secret}.jpg _b per immagine grande
    #d = {'gallery_photos': photo_data['photos']['photo']}
    #photo_list=photo_data['photos']['photo']
    #return photo_data['photos']['photo'][0]['id']
    csv = """"question","url","uri","url_b"
"""
    current = 0
    max=int(photo_data['photos']['total'])
    while current < max:
        csv = csv+"""flickr,https://farm"""+str(photo_data['photos']['photo'][current]['farm'])+""".staticflickr.com/"""+str(photo_data['photos']['photo'][current]['server'])+"""/"""+str(photo_data['photos']['photo'][current]['id'])+"""_"""+str(photo_data['photos']['photo'][current]['secret'])+"""_b.jpg,"""+str(gallery_url)+""",https://farm"""+str(photo_data['photos']['photo'][current]['farm'])+""".staticflickr.com/"""+str(photo_data['photos']['photo'][current]['server'])+"""/"""+str(photo_data['photos']['photo'][current]['id'])+"""_"""+str(photo_data['photos']['photo'][current]['secret'])+"""_b.jpg
"""
        current +=1
    #while current < max
    #    csv = photo_data['photos']['photo'][current]['id']
    #    current +=1
    # We need to modify the response, so the first thing we 
    # need to do is create a response out of the CSV string
    #ret_res = make_response(json.dumps(photo_data))
    # This is the key: Set the right header for the response
    # to be downloaded, instead of just printed on the browser
    #response.headers["Content-Disposition"] = "attachment; filename=books.csv"
    #return Response(csv, mimetype="text/csv", content_type="text/csv; name='filename.csv'")
    return Response(csv, mimetype="text/csv")
    #return ret_res
    #return render_template("/home/get_flickr_gallery.html", **d)

@app.route("/add_one_spam")
def add_one_spam():
    task_id=request.args.get('task_id', None)
    query = text(''' UPDATE task SET is_it_spam=is_it_spam+1 WHERE id=:task_id ''')
    rows = db.engine.execute(query, task_id=task_id)
    return render_template("/home/about.html")

@app.route("/get_flickr_set")
def get_flickr_set():
    #d = {'gallery_url': request.args.get('gallery_url', None) }
    #d = {'gallery_url': "a"}
    gallery_id=request.args.get('set_url', None)
    #print data
    response2 = urllib2.urlopen('https://api.flickr.com/services/rest/?method=flickr.photosets.getPhotos&api_key=440a683988a7da58f576256cb68bc270&photoset_id='+gallery_id+'&format=json&nojsoncallback=1')
    photo_data = json.load(response2)
    #return json.dumps(photo_data)
    #https://farm{farm-id}.staticflickr.com/{server-id}/{id}_{secret}.jpg _b per immagine grande
    #d = {'gallery_photos': photo_data['photos']['photo']}
    #photo_list=photo_data['photos']['photo']
    #return photo_data['photos']['photo'][0]['id']
    csv = """"question","url","uri","url_b"
"""
    current = 0
    max=int(photo_data['photoset']['total'])
    while current < max:
        csv = csv+"""flickr,https://farm"""+str(photo_data['photoset']['photo'][current]['farm'])+""".staticflickr.com/"""+str(photo_data['photoset']['photo'][current]['server'])+"""/"""+str(photo_data['photoset']['photo'][current]['id'])+"""_"""+str(photo_data['photoset']['photo'][current]['secret'])+"""_b.jpg,https://www.flickr.com/photos/"""+str(photo_data['photoset']['owner'])+"""/sets/"""+str(gallery_id)+"""/,https://farm"""+str(photo_data['photoset']['photo'][current]['farm'])+""".staticflickr.com/"""+str(photo_data['photoset']['photo'][current]['server'])+"""/"""+str(photo_data['photoset']['photo'][current]['id'])+"""_"""+str(photo_data['photoset']['photo'][current]['secret'])+"""_b.jpg
"""
        current +=1
    #while current < max
    #    csv = photo_data['photos']['photo'][current]['id']
    #    current +=1
    # We need to modify the response, so the first thing we 
    # need to do is create a response out of the CSV string
    #ret_res = make_response(json.dumps(photo_data))
    # This is the key: Set the right header for the response
    # to be downloaded, instead of just printed on the browser
    #response.headers["Content-Disposition"] = "attachment; filename=books.csv"
    #return Response(csv, mimetype="text/csv", content_type="text/csv; name='filename.csv'")
    return Response(csv, mimetype="text/csv")
    #return ret_res
    #return render_template("/home/get_flickr_gallery.html", **d)

@app.route("/search")
def search():
    """Render search results page"""
    return render_template("/home/search.html")

def get_port():
    port = os.environ.get('PORT', '')
    if port.isdigit():
        return int(port)
    else:
        return app.config['PORT']

if __name__ == "__main__":
    logging.basicConfig(level=logging.NOTSET)
    app.run(host=app.config['HOST'], port=get_port(),
            debug=app.config.get('DEBUG', True))
