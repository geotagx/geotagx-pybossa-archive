from base import model, db, web, Fixtures
from helper.user import User


class Helper(object):
    """Class to help testing the web interface"""

    user = User()
    project_short_name = "sampleproject"

    def setUp(self):
        self.app = web.app.test_client()
        model.rebuild_db()

    def tearDown(self):
        db.session.remove()

    @classmethod
    def teardown_class(cls):
        model.rebuild_db()

    def html_title(self, title=None):
        """Helper function to create an HTML title"""
        if title is None:
            return "<title>PyBossa</title>"
        else:
            return "<title>PyBossa &middot; %s</title>" % title

    def register(self, method="POST", fullname="John Doe", username="johndoe",
                 password="p4ssw0rd", password2=None, email=None):
        """Helper function to register and sign in a user"""
        if password2 is None:
            password2 = password
        if email is None:
            email = username + '@example.com'
        if method == "POST":
            return self.app.post('/account/register',
                                 data={
                                     'fullname': fullname,
                                     'username': username,
                                     'email_addr': email,
                                     'password': password,
                                     'confirm': password2},
                                 follow_redirects=True)
        else:
            return self.app.get('/account/register', follow_redirects=True)

    def signin(self, method="POST", email="johndoe@example.com", password="p4ssw0rd",
               next=None):
        """Helper function to sign in current user"""
        url = '/account/signin'
        if next is not None:
            url = url + '?next=' + next
        if method == "POST":
            return self.app.post(url, data={'email': email,
                                            'password': password},
                                 follow_redirects=True)
        else:
            return self.app.get(url, follow_redirects=True)

    def profile(self):
        """Helper function to check profile of signed in user"""
        return self.app.get("/account/profile", follow_redirects=True)

    def update_profile(self, method="POST", id=1, fullname="John Doe",
                       name="johndoe", locale="es", email_addr="johndoe@example.com"):
        """Helper function to update the profile of users"""
        if (method == "POST"):
            return self.app.post("/account/profile/update",
                                 data={'id': id,
                                       'fullname': fullname,
                                       'name': name,
                                       'locale': locale,
                                       'email_addr': email_addr},
                                 follow_redirects=True)
        else:
            return self.app.get("/account/profile/update",
                                follow_redirects=True)

    def signout(self):
        """Helper function to sign out current user"""
        return self.app.get('/account/signout', follow_redirects=True)

    def create_categories(self):
        categories = db.session.query(model.Category).all()
        if len(categories) == 0:
            print "Categories 0"
            print "Creating default ones"
            Fixtures.create_categories()

    def new_project(self, method="POST", name="Sample Project",
                        short_name="sampleproject", description="Description",
                        thumbnail='An Icon link',
                        allow_anonymous_contributors='True',
                        category_id="1",
                        long_description=u'<div id="long_desc">Long desc</div>',
                        hidden=False):
        """Helper function to create an project"""
        if method == "POST":
            self.create_categories()
            if hidden:
                return self.app.post("/project/new", data={
                    'name': name,
                    'short_name': short_name,
                    'description': description,
                    'thumbnail': thumbnail,
                    'allow_anonymou_contributors': allow_anonymous_contributors,
                    'category_id': category_id,
                    'long_description': long_description,
                    'hidden': hidden,
                }, follow_redirects=True)
            else:
                return self.app.post("/project/new", data={
                    'name': name,
                    'short_name': short_name,
                    'description': description,
                    'thumbnail': thumbnail,
                    'allow_anonymous_contributors': allow_anonymous_contributors,
                    'category_id': category_id,
                    'long_description': long_description,
                }, follow_redirects=True)
        else:
            return self.app.get("/project/new", follow_redirects=True)

    def new_task(self, projectid):
        """Helper function to create tasks for an project"""
        tasks = []
        for i in range(0, 10):
            tasks.append(model.Task(project_id=projectid, state='0', info={}))
        db.session.add_all(tasks)
        db.session.commit()

    def delTaskRuns(self, project_id=1):
        """Deletes all TaskRuns for a given project_id"""
        db.session.query(model.TaskRun).filter_by(project_id=1).delete()
        db.session.commit()

    def task_settings_scheduler(self, method="POST", short_name='sampleproject',
                                sched="default"):
        """Helper function to modify task scheduler"""
        url = "/project/%s/tasks/scheduler" % short_name
        if method == "POST":
            return self.app.post(url, data={
                'sched': sched,
            }, follow_redirects=True)
        else:
            return self.app.get(url, follow_redirects=True)

    def task_settings_redundancy(self, method="POST", short_name='sampleproject',
                                 n_answers=30):
        """Helper function to modify task redundancy"""
        url = "/project/%s/tasks/redundancy" % short_name
        if method == "POST":
            return self.app.post(url, data={
                'n_answers': n_answers,
            }, follow_redirects=True)
        else:
            return self.app.get(url, follow_redirects=True)

    def delete_project(self, method="POST", short_name="sampleproject"):
        """Helper function to create an project"""
        if method == "POST":
            return self.app.post("/project/%s/delete" % short_name,
                                 follow_redirects=True)
        else:
            return self.app.get("/project/%s/delete" % short_name,
                                follow_redirects=True)

    def update_project(self, method="POST", short_name="sampleproject", id=1,
                           new_name="Sample Project", new_short_name="sampleproject",
                           new_description="Description",
                           new_thumbnail="New Icon link",
                           new_allow_anonymous_contributors="False",
                           new_category_id="2",
                           new_long_description="Long desc",
                           new_sched="random",
                           new_hidden=False):
        """Helper function to create an project"""
        if method == "POST":
            if new_hidden:
                return self.app.post("/project/%s/update" % short_name,
                                     data={
                                         'id': id,
                                         'name': new_name,
                                         'short_name': new_short_name,
                                         'description': new_description,
                                         'thumbnail': new_thumbnail,
                                         'allow_anonymous_contributors': new_allow_anonymous_contributors,
                                         'category_id': new_category_id,
                                         'long_description': new_long_description,
                                         'sched': new_sched,
                                         'hidden': new_hidden},
                                     follow_redirects=True)
            else:
                return self.app.post("/project/%s/update" % short_name,
                                     data={'id': id, 'name': new_name,
                                           'short_name': new_short_name,
                                           'thumbnail': new_thumbnail,
                                           'allow_anonymous_contributors': new_allow_anonymous_contributors,
                                           'category_id': new_category_id,
                                           'long_description': new_long_description,
                                           'sched': new_sched,
                                           'description': new_description},
                                     follow_redirects=True)
        else:
            return self.app.get("/project/%s/update" % short_name,
                                follow_redirects=True)
