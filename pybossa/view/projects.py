# This file is part of PyBOSSA.
#
# PyBOSSA is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# PyBOSSA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with PyBOSSA.  If not, see <http://www.gnu.org/licenses/>.

from StringIO import StringIO
from flask import Blueprint, request, url_for, flash, redirect, abort, Response, current_app
from flask import render_template, make_response
from flaskext.wtf import Form, IntegerField, TextField, BooleanField, \
    SelectField, validators, HiddenInput, TextAreaField
from flaskext.login import login_required, current_user
from flaskext.babel import lazy_gettext
from werkzeug.exceptions import HTTPException
from sqlalchemy.sql import text

import pybossa.model as model
import pybossa.stats as stats
import pybossa.validator as pb_validator

from pybossa.core import db
from pybossa.model import Project, Task
from pybossa.util import Pagination, UnicodeWriter, admin_required
from pybossa.auth import require
from pybossa.cache import projects as cached_projects
from pybossa.cache import categories as cached_cat
from pybossa.ckan import Ckan

import json
import importer
import presenter as presenter_module
import operator
import math
import requests

blueprint = Blueprint('project', __name__)


class ProjectForm(Form):
    id = IntegerField(label=None, widget=HiddenInput())
    name = TextField(lazy_gettext('Name'),
                     [validators.Required(),
                      pb_validator.Unique(db.session, model.Project, model.Project.name,
                                          message="Name is already taken.")])
    short_name = TextField(lazy_gettext('Short Name'),
                           [validators.Required(),
                            pb_validator.NotAllowedChars(),
                            pb_validator.Unique(
                                db.session, model.Project, model.Project.short_name,
                                message=lazy_gettext(
                                    "Short Name is already taken."))])
    description = TextField(lazy_gettext('Description'),
                            [validators.Required(
                                message=lazy_gettext(
                                    "You must provide a description."))])
    thumbnail = TextField(lazy_gettext('Icon Link'))
    allow_anonymous_contributors = SelectField(
        lazy_gettext('Allow Anonymous Contributors'),
        choices=[('True', lazy_gettext('Yes')),
                 ('False', lazy_gettext('No'))])
    category_id = SelectField(lazy_gettext('Category'), coerce=int)
    long_description = TextAreaField(lazy_gettext('Long Description'))
    hidden = BooleanField(lazy_gettext('Hide?'))


class TaskPresenterForm(Form):
    id = IntegerField(label=None, widget=HiddenInput())
    editor = TextAreaField('')


class TaskRedundancyForm(Form):
    n_answers = IntegerField(lazy_gettext('Redundancy'),
                             [validators.Required(),
                              validators.NumberRange(
                                  min=1, max=1000,
                                  message=lazy_gettext('Number of answers should be a \
                                                       value between 1 and 1,000'))])


class TaskSchedulerForm(Form):
    sched = SelectField(lazy_gettext('Task Scheduler'),
                        choices=[('default', lazy_gettext('Default')),
                                 ('breadth_first', lazy_gettext('Breadth First')),
                                 ('depth_first', lazy_gettext('Depth First')),
                                 ('random', lazy_gettext('Random'))],)


def project_title(project, page_name):
    if not project:
        return "Project not found"
    if page_name is None:
        return "Project: %s" % (project.name)
    return "Project: %s &middot; %s" % (project.name, page_name)


def project_by_shortname(short_name):
    return Project.query.filter_by(short_name=short_name).first_or_404()


@blueprint.route('/', defaults={'page': 1})
@blueprint.route('/page/<int:page>/', defaults={'page': 1})
def redirect_old_featured(page):
    """DEPRECATED only to redirect old links"""
    return redirect(url_for('.index', page=page), 301)


@blueprint.route('/published/', defaults={'page': 1})
@blueprint.route('/published/<int:page>/', defaults={'page': 1})
def redirect_old_published(page):
    """DEPRECATED only to redirect old links"""
    category = db.session.query(model.Category).first()
    return redirect(url_for('.project_cat_index', category=category.short_name, page=page), 301)


@blueprint.route('/draft/', defaults={'page': 1})
@blueprint.route('/draft/<int:page>/', defaults={'page': 1})
def redirect_old_draft(page):
    """DEPRECATED only to redirect old links"""
    return redirect(url_for('.draft', page=page), 301)


@blueprint.route('/category/featured/', defaults={'page': 1})
@blueprint.route('/category/featured/page/<int:page>/')
def index(page):
    """List projects in the system"""
    if cached_projects.n_featured() > 0:
        return project_index(page, cached_projects.get_featured, 'featured',
                         True, False)
    else:
        categories = cached_cat.get_all()
        if len(categories) > 0:
            cat_short_name = categories[0].short_name
        else:
            cat = db.session.query(model.Category).first()
            if cat:
                cat_short_name = cat.short_name
            else:
                cat_short_name = "algo"
        return redirect(url_for('.project_cat_index', category=cat_short_name))


def project_index(page, lookup, category, fallback, use_count):
    """Show projects of project_type"""
    if not require.project.read():
        abort(403)

    per_page = 5

    projects, count = lookup(category, page, per_page)

    if fallback and not projects:
        return redirect(url_for('.published'))

    pagination = Pagination(page, per_page, count)
    categories = cached_cat.get_all()
    # Check for pre-defined categories featured and draft
    featured_cat = model.Category(name='Featured',
                                  short_name='featured',
                                  description='Featured projects')
    if category == 'featured':
        active_cat = featured_cat
    elif category == 'draft':
        active_cat = model.Category(name='Draft',
                                    short_name='draft',
                                    description='Draft projects')
    else:
        active_cat = db.session.query(model.Category)\
                       .filter_by(short_name=category).first()

    # Check if we have to add the section Featured to local nav
    if cached_projects.n_featured() > 0:
        categories.insert(0, featured_cat)
    template_args = {
        "projects": projects,
        "title": lazy_gettext("Projects"),
        "pagination": pagination,
        "active_cat": active_cat,
        "categories": categories}

    if use_count:
        template_args.update({"count": count})
    return render_template('/projects/index.html', **template_args)


@blueprint.route('/category/draft/', defaults={'page': 1})
@blueprint.route('/category/draft/page/<int:page>/')
@login_required
@admin_required
def draft(page):
    """Show the Draft projects"""
    return project_index(page, cached_projects.get_draft, 'draft',
                     False, True)


@blueprint.route('/category/<string:category>/', defaults={'page': 1})
@blueprint.route('/category/<string:category>/page/<int:page>/')
def project_cat_index(category, page):
    """Show Projects that belong to a given category"""
    return project_index(page, cached_projects.get, category, False, True)


@blueprint.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    if not require.project.create():
        abort(403)
    form = ProjectForm(request.form)
    categories = db.session.query(model.Category).all()
    form.category_id.choices = [(c.id, c.name) for c in categories]

    def respond(errors):
        return render_template('projects/new.html',
                               title=lazy_gettext("Create an Project"),
                               form=form, errors=errors)

    if request.method != 'POST':
        return respond(False)

    if not form.validate():
        flash(lazy_gettext('Please correct the errors'), 'error')
        return respond(True)

    info = {}
    # Add the info items
    if form.thumbnail.data:
        info['thumbnail'] = form.thumbnail.data

    project = model.Project(name=form.name.data,
                    short_name=form.short_name.data,
                    description=form.description.data,
                    long_description=form.long_description.data,
                    category_id=form.category_id.data,
                    allow_anonymous_contributors=form.allow_anonymous_contributors.data,
                    hidden=int(form.hidden.data),
                    owner_id=current_user.id,
                    info=info,)

    cached_projects.reset()
    db.session.add(project)
    db.session.commit()
    # Clean cache
    msg_1 = lazy_gettext('Project created!')
    flash('<i class="icon-ok"></i> ' + msg_1, 'success')
    flash('<i class="icon-bullhorn"></i> ' +
          lazy_gettext('You can check the ') +
          '<strong><a href="https://docs.pybossa.com">' +
          lazy_gettext('Guide and Documentation') +
          '</a></strong> ' +
          lazy_gettext('for adding tasks, a thumbnail, using PyBossa.JS, etc.'),
          'info')
    return redirect(url_for('.settings', short_name=project.short_name))


@blueprint.route('/<short_name>/tasks/taskpresentereditor', methods=['GET', 'POST'])
@login_required
def task_presenter_editor(short_name):
    errors = False
    project = project_by_shortname(short_name)

    title = project_title(project, "Task Presenter Editor")
    if not require.project.update(project):
        abort(403)

    form = TaskPresenterForm(request.form)
    if request.method == 'POST' and form.validate():
        project.info['task_presenter'] = form.editor.data
        db.session.add(project)
        db.session.commit()
        msg_1 = lazy_gettext('Task presenter added!')
        flash('<i class="icon-ok"></i> ' + msg_1, 'success')
        return redirect(url_for('.tasks', short_name=project.short_name))

    if request.method == 'POST' and not form.validate():
        flash(lazy_gettext('Please correct the errors'), 'error')
        errors = True

    if request.method != 'GET':
        return

    if project.info.get('task_presenter'):
        form.editor.data = project.info['task_presenter']
    else:
        if not request.args.get('template'):
            msg_1 = lazy_gettext('<strong>Note</strong> You will need to upload the'
                                 ' tasks using the')
            msg_2 = lazy_gettext('CSV importer')
            msg_3 = lazy_gettext(' or download the project bundle and run the'
                                 ' <strong>createTasks.py</strong> script in your'
                                 ' computer')
            url = '<a href="%s"> %s</a>' % (url_for('project.import_task',
                                                    short_name=project.short_name), msg_2)
            msg = msg_1 + url + msg_3
            flash(msg, 'info')

            wrap = lambda i: "projects/presenters/%s.html" % i
            pres_tmpls = map(wrap, presenter_module.presenters)

            return render_template(
                'projects/task_presenter_options.html',
                title=title,
                project=project,
                presenters=pres_tmpls)

        tmpl_uri = "projects/snippets/%s.html" \
            % request.args.get('template')
        tmpl = render_template(tmpl_uri, project=project)
        form.editor.data = tmpl
        msg = 'Your code will be <em>automagically</em> rendered in \
                      the <strong>preview section</strong>. Click in the \
                      preview button!'
        flash(lazy_gettext(msg), 'info')
    return render_template('projects/task_presenter_editor.html',
                           title=title,
                           form=form,
                           project=project,
                           errors=errors)


@blueprint.route('/<short_name>/delete', methods=['GET', 'POST'])
@login_required
def delete(short_name):
    project = project_by_shortname(short_name)
    title = project_title(project, "Delete")
    if not require.project.delete(project):
        abort(403)
    if request.method == 'GET':
        return render_template('/projects/delete.html',
                               title=title,
                               project=project)
    # Clean cache
    cached_projects.clean(project.id)
    db.session.delete(project)
    db.session.commit()
    flash(lazy_gettext('Project deleted!'), 'success')
    return redirect(url_for('account.profile'))


@blueprint.route('/<short_name>/update', methods=['GET', 'POST'])
@login_required
def update(short_name):
    project = project_by_shortname(short_name)

    def handle_valid_form(form):
        hidden = int(form.hidden.data)

        new_info = {}
        # Add the info items
        project = project_by_shortname(short_name)
        if form.thumbnail.data:
            new_info['thumbnail'] = form.thumbnail.data
        #if form.sched.data:
        #    new_info['sched'] = form.sched.data

        # Merge info object
        info = dict(project.info.items() + new_info.items())

        new_project = model.Project(
            id=form.id.data,
            name=form.name.data,
            short_name=form.short_name.data,
            description=form.description.data,
            long_description=form.long_description.data,
            hidden=hidden,
            info=info,
            owner_id=project.owner_id,
            allow_anonymous_contributors=form.allow_anonymous_contributors.data,
            category_id=form.category_id.data)

        project = project_by_shortname(short_name)
        db.session.merge(new_project)
        db.session.commit()
        cached_projects.reset()
        cached_cat.reset()
        flash(lazy_gettext('Project updated!'), 'success')
        return redirect(url_for('.details',
                                short_name=new_project.short_name))

    if not require.project.update(project):
        abort(403)

    title = project_title(project, "Update")
    if request.method == 'GET':
        form = ProjectForm(obj=project)
        categories = db.session.query(model.Category).all()
        form.category_id.choices = [(c.id, c.name) for c in categories]
        if project.category_id is None:
            project.category_id = categories[0].id
        form.populate_obj(project)
        if project.info.get('thumbnail'):
            form.thumbnail.data = project.info['thumbnail']
        #if project.info.get('sched'):
        #    for s in form.sched.choices:
        #        if project.info['sched'] == s[0]:
        #            form.sched.data = s[0]
        #            break

    if request.method == 'POST':
        form = ProjectForm(request.form)
        categories = cached_cat.get_all()
        form.category_id.choices = [(c.id, c.name) for c in categories]
        if form.validate():
            return handle_valid_form(form)
        flash(lazy_gettext('Please correct the errors'), 'error')

    return render_template('/projects/update.html',
                           form=form,
                           title=title,
                           project=project)


@blueprint.route('/<short_name>/')
def details(short_name):
    project = project_by_shortname(short_name)

    try:
        require.project.read(project)
        require.project.update(project)
        template = '/projects/actions.html'
    except HTTPException:
        if project.hidden:
            project = None
        template = '/projects/project.html'

    title = project_title(project, None)
    template_args = {"project": project, "title": title}
    try:
        if current_app.config.get('CKAN_URL'):
            template_args['ckan_name'] = current_app.config.get('CKAN_NAME')
            ckan = Ckan(url=current_app.config['CKAN_URL'])
            pkg, e = ckan.package_exists(name=short_name)
            if e:
                raise e
            if pkg:
                template_args['ckan_pkg_url'] = (
                    "%s/dataset/%s" % (current_app.config['CKAN_URL'], short_name))
                template_args['ckan_pkg'] = pkg
    except requests.exceptions.ConnectionError:
        current_app.logger.error("CKAN server down or there is a typo in the URL")
    except Exception as e:
        current_app.logger.error(e)

    return render_template(template, **template_args)


@blueprint.route('/<short_name>/settings')
@login_required
def settings(short_name):
    project = project_by_shortname(short_name)

    title = project_title(project, "Settings")
    try:
        require.project.read(project)
        require.project.update(project)

        return render_template('/projects/settings.html',
                               project=project,
                               title=title)
    except HTTPException:
        return abort(403)


def compute_importer_variant_pairs(forms):
    """Return a list of pairs of importer variants. The pair-wise enumeration
    is due to UI design.
    """
    variants = reduce(operator.__add__,
                      [i.variants for i in forms.itervalues()],
                      [])
    if len(variants) % 2:
        variants.append("empty")

    prefix = "projects/tasks/"

    importer_variants = map(lambda i: "%s%s.html" % (prefix, i), variants)
    return [
        (importer_variants[i * 2], importer_variants[i * 2 + 1])
        for i in xrange(0, int(math.ceil(len(variants) / 2.0)))]


@blueprint.route('/<short_name>/tasks/import', methods=['GET', 'POST'])
@login_required
def import_task(short_name):
    project = project_by_shortname(short_name)
    title = project_title(project, "Import Tasks")
    loading_text = lazy_gettext("Importing tasks, this may take a while, wait...")
    template_args = {"title": title, "project": project, "loading_text": loading_text}
    if not require.project.update(project):
        return abort(403)
    data_handlers = dict([
        (i.template_id, (i.form_detector, i(request.form), i.form_id))
        for i in importer.importers])
    forms = [
        (i.form_id, i(request.form))
        for i in importer.importers]
    forms = dict(forms)
    template_args.update(forms)

    template_args["importer_variants"] = compute_importer_variant_pairs(forms)

    template = request.args.get('template')

    if not (template or request.method == 'POST'):
        return render_template('/projects/import_options.html',
                               **template_args)

    if template == 'gdocs':
        mode = request.args.get('mode')
        if mode is not None:
            template_args["gdform"].googledocs_url.data = importer.googledocs_urls[mode]

    # in future, we shall pass an identifier of the form/template used,
    # which we can receive here, and use for a dictionary lookup, rather than
    # this search mechanism
    form = None
    handler = None
    for k, v in data_handlers.iteritems():
        field_id, handler, form_name = v
        if field_id in request.form:
            form = template_args[form_name]
            template = k
            break

    def render_forms():
        tmpl = '/projects/importers/%s.html' % template
        return render_template(tmpl, **template_args)

    if not (form and form.validate_on_submit()):
        return render_forms()

    return _import_task(project, handler, form, render_forms)


def _import_task(project, handler, form, render_forms):
    try:
        empty = True
        for task_data in handler.tasks(form):
            task = model.Task(project=project)
            print task_data
            [setattr(task, k, v) for k, v in task_data.iteritems()]
            db.session.add(task)
            db.session.commit()
            empty = False
        if empty:
            raise importer.BulkImportException(
                lazy_gettext('Oops! It looks like the file is empty.'))
        flash(lazy_gettext('Tasks imported successfully!'), 'success')
        return redirect(url_for('.tasks', short_name=project.short_name))
    except importer.BulkImportException, err_msg:
        flash(err_msg, 'error')
    except Exception as inst:
        print inst
        msg = 'Oops! Looks like there was an error with processing that file!'
        flash(lazy_gettext(msg), 'error')
    return render_forms()


@blueprint.route('/<short_name>/task/<int:task_id>')
def task_presenter(short_name, task_id):
    project = project_by_shortname(short_name)
    task = Task.query.filter_by(id=task_id).first_or_404()

    if current_user.is_anonymous():
        if not project.allow_anonymous_contributors:
            msg = ("Oops! You have to sign in to participate in "
                   "<strong>%s</strong>"
                   "project" % project.name)
            flash(lazy_gettext(msg), 'warning')
            return redirect(url_for('account.signin',
                                    next=url_for('.presenter',
                                                 short_name=project.short_name)))
        else:
            msg_1 = lazy_gettext(
                "Ooops! You are an anonymous user and will not "
                "get any credit"
                " for your contributions.")
            next_url = url_for(
                'project.task_presenter',
                short_name=short_name,
                task_id=task_id)
            url = url_for(
                'account.signin',
                next=next_url)
            flash(msg_1 + "<a href=\"" + url + "\">Sign in now!</a>", "warning")

    title = project_title(project, "Contribute")
    template_args = {"project": project, "title": title}

    def respond(tmpl):
        return render_template(tmpl, **template_args)

    if not (task.project_id == project.id):
        return respond('/projects/task/wrong.html')

    #return render_template('/projects/presenter.html', project = project)
    # Check if the user has submitted a task before

    tr_search = db.session.query(model.TaskRun)\
                  .filter(model.TaskRun.task_id == task_id)\
                  .filter(model.TaskRun.project_id == project.id)

    if current_user.is_anonymous():
        remote_addr = request.remote_addr or "127.0.0.1"
        tr = tr_search.filter(model.TaskRun.user_ip == remote_addr)
    else:
        tr = tr_search.filter(model.TaskRun.user_id == current_user.id)

    tr_first = tr.first()
    if tr_first is None:
        return respond('/projects/presenter.html')
    else:
        return respond('/projects/task/done.html')


@blueprint.route('/<short_name>/presenter')
@blueprint.route('/<short_name>/newtask')
def presenter(short_name):
    project = project_by_shortname(short_name)
    title = project_title(project, "Contribute")
    template_args = {"project": project, "title": title}

    if not project.allow_anonymous_contributors and current_user.is_anonymous():
        msg = "Oops! You have to sign in to participate in <strong>%s</strong> \
               project" % project.name
        flash(lazy_gettext(msg), 'warning')
        return redirect(url_for('account.signin',
                        next=url_for('.presenter', short_name=project.short_name)))

    msg = "Ooops! You are an anonymous user and will not \
           get any credit for your contributions. Sign in \
           now!"

    def respond(tmpl):
        if (current_user.is_anonymous()):
            msg_1 = lazy_gettext(msg)
            flash(msg_1, "warning")
        resp = make_response(render_template(tmpl, **template_args))
        return resp

    if project.info.get("tutorial") and \
            request.cookies.get(project.short_name + "tutorial") is None:
        resp = respond('/projects/tutorial.html')
        resp.set_cookie(project.short_name + 'tutorial', 'seen')
        return resp
    else:
        return respond('/projects/presenter.html')


@blueprint.route('/<short_name>/tutorial')
def tutorial(short_name):
    project = project_by_shortname(short_name)
    title = project_title(project, "Tutorial")
    return render_template('/projects/tutorial.html', title=title, project=project)


@blueprint.route('/<short_name>/<int:task_id>/results.json')
def export(short_name, task_id):
    """Return a file with all the TaskRuns for a give Task"""
    project_by_shortname(short_name)
    task = db.session.query(model.Task)\
        .filter(model.Task.id == task_id)\
        .first()

    results = [tr.dictize() for tr in task.task_runs]
    return Response(json.dumps(results), mimetype='application/json')


@blueprint.route('/<short_name>/tasks/')
def tasks(short_name):
    project = project_by_shortname(short_name)
    title = project_title(project, "Tasks")
    try:
        require.project.read(project)
        return render_template('/projects/tasks.html',
                               title=title,
                               project=project)
    except HTTPException:
        if not project.hidden:
            return render_template('/projects/tasks.html',
                                   title="Project not found",
                                   project=None)
        return render_template('/projects/tasks.html',
                               title="Project not found",
                               project=None)


@blueprint.route('/<short_name>/tasks/browse', defaults={'page': 1})
@blueprint.route('/<short_name>/tasks/browse/<int:page>')
def tasks_browse(short_name, page):
    project = project_by_shortname(short_name)
    title = project_title(project, "Tasks")

    def respond():
        per_page = 10
        count = db.session.query(model.Task)\
            .filter_by(project_id=project.id)\
            .count()
        project_tasks = db.session.query(model.Task)\
            .filter_by(project_id=project.id)\
            .order_by(model.Task.id)\
            .limit(per_page)\
            .offset((page - 1) * per_page)\
            .all()

        if not project_tasks and page != 1:
            abort(404)

        pagination = Pagination(page, per_page, count)
        return render_template('/projects/tasks_browse.html',
                               project=project,
                               tasks=project_tasks,
                               title=title,
                               pagination=pagination)

    try:
        require.project.read(project)
        require.project.update(project)
        return respond()
    except HTTPException:
        if not project.hidden:
            return respond()
        return render_template('/projects/tasks.html',
                               title="Project not found",
                               project=None)


@blueprint.route('/<short_name>/tasks/delete', methods=['GET', 'POST'])
@login_required
def delete_tasks(short_name):
    """Delete ALL the tasks for a given project"""
    project = project_by_shortname(short_name)
    try:
        require.project.read(project)
        require.project.update(project)
        if request.method == 'GET':
            title = project_title(project, "Delete")
            return render_template('projects/tasks/delete.html',
                                   project=project,
                                   title=title)
        else:
            for task in project.tasks:
                db.session.delete(task)
            db.session.commit()
            msg = "All the tasks and associated task runs have been deleted"
            flash(lazy_gettext(msg), 'success')
            return redirect(url_for('.tasks', short_name=project.short_name))
    except HTTPException:
        return abort(403)


@blueprint.route('/<short_name>/tasks/export')
def export_to(short_name):
    """Export Tasks and TaskRuns in the given format"""
    project = project_by_shortname(short_name)
    title = project_title(project, lazy_gettext("Export"))
    loading_text = lazy_gettext("Exporting data..., this may take a while")

    def respond():
        return render_template('/projects/export.html',
                               title=title,
                               loading_text=loading_text,
                               project=project)

    def gen_json(table):
        n = db.session.query(table)\
            .filter_by(project_id=project.id).count()
        sep = ", "
        yield "["
        for i, tr in enumerate(db.session.query(table)
                                 .filter_by(project_id=project.id).yield_per(1), 1):
            item = json.dumps(tr.dictize())
            if (i == n):
                sep = ""
            yield item + sep
        yield "]"

    def handle_task(writer, t):
        writer.writerow(t.info.values())

    def handle_task_run(writer, t):
        if (type(t.info) == dict):
            writer.writerow(t.info.values())
        else:
            writer.writerow([t.info])

    def get_csv(out, writer, table, handle_row):
        for tr in db.session.query(table)\
                .filter_by(project_id=project.id)\
                .yield_per(1):
            handle_row(writer, tr)
        yield out.getvalue()

    def respond_json(ty):
        tables = {"task": model.Task, "task_run": model.TaskRun}
        try:
            table = tables[ty]
        except KeyError:
            return abort(404)
        return Response(gen_json(table), mimetype='application/json')

    def create_ckan_datastores(ckan):
        tables = {"task": model.Task, "task_run": model.TaskRun}
        resources = dict(task=None, task_run=None)
        for k in tables.keys():
            # Create the two table resources
            resource = ckan.resource_create(name=k)
            resources[k] = resource['result']
            ckan.datastore_create(name=k, resource_id=resources[k]['id'])
        return resources

    def respond_ckan(ty):
        # First check if there is a package (dataset) in CKAN
        tables = {"task": model.Task, "task_run": model.TaskRun}
        msg_1 = lazy_gettext("Data exported to ")
        msg = msg_1 + "%s ..." % current_app.config['CKAN_URL']
        ckan = Ckan(url=current_app.config['CKAN_URL'],
                    api_key=current_user.ckan_api)
        project_url = url_for('.details', short_name=project.short_name, _external=True)

        try:
            package, e = ckan.package_exists(name=project.short_name)
            if e:
                raise e
            if package:
                # Update the package
                ckan.package_update(project=project, user=project.owner, url=project_url)
                if len(package['resources']) == 0:
                    resources = create_ckan_datastores(ckan)
                    ckan.datastore_upsert(name=ty,
                                          records=gen_json(tables[ty]),
                                          resource_id=resources[ty]['id'])
                else:
                    ckan.datastore_delete(name=ty)
                    ckan.datastore_create(name=ty)
                    ckan.datastore_upsert(name=ty, records=gen_json(tables[ty]))
            else:
                ckan.package_create(project=project, user=project.owner, url=project_url,
                                    tags=current_app.config['BRAND'])
                resources = create_ckan_datastores(ckan)
                ckan.datastore_upsert(name=ty,
                                      records=gen_json(tables[ty]),
                                      resource_id=resources[ty]['id'])

            flash(msg, 'success')
            return respond()
        except requests.exceptions.ConnectionError:
                msg = "CKAN server seems to be down, try again layer or contact the CKAN admins"
                current_app.logger.error(msg)
                flash(msg, 'danger')
        except Exception as inst:
            if len(inst.args) == 3:
                type, msg, status_code = inst.args
                msg = ("Error: %s with status code: %s" % (type, status_code))
            else:
                msg = ("Error: %s" % inst.args[0])
            current_app.logger.error(msg)
            flash(msg, 'danger')
        finally:
            return respond()

    def respond_csv(ty):
        # Export Task(/Runs) to CSV
        types = {
            "task": (
                model.Task, handle_task,
                (lambda x: True),
                lazy_gettext(
                    "Oops, the project does not have tasks to \
                           export, if you are the owner add some tasks")),
            "task_run": (
                model.TaskRun, handle_task_run,
                (lambda x: type(x.info) == dict),
                lazy_gettext(
                    "Oops, there are no Task Runs yet to export, invite \
                           some users to participate"))}
        try:
            table, handle_row, test, msg = types[ty]
        except KeyError:
            return abort(404)

        out = StringIO()
        writer = UnicodeWriter(out)
        t = db.session.query(table)\
            .filter_by(project_id=project.id)\
            .first()
        if t is not None:
            if test(t):
                writer.writerow(t.info.keys())

            return Response(get_csv(out, writer, table, handle_row),
                            mimetype='text/csv')
        else:
            flash(msg, 'info')
            return respond()

    export_formats = ["json", "csv"]
    if current_user.is_authenticated():
        if current_user.ckan_api:
            export_formats.append('ckan')

    ty = request.args.get('type')
    fmt = request.args.get('format')
    if not (fmt and ty):
        if len(request.args) >= 1:
            abort(404)
        return render_template('/projects/export.html',
                               title=title,
                               loading_text=loading_text,
                               ckan_name=current_app.config.get('CKAN_NAME'),
                               project=project)
    if fmt not in export_formats:
        abort(404)
    return {"json": respond_json, "csv": respond_csv, 'ckan': respond_ckan}[fmt](ty)


@blueprint.route('/<short_name>/stats')
def show_stats(short_name):
    """Returns Project Stats"""
    project = project_by_shortname(short_name)
    title = project_title(project, "Statistics")

    if not (len(project.tasks) > 0 and len(project.task_runs) > 0):
        return render_template('/projects/non_stats.html',
                               title=title,
                               project=project)

    dates_stats, hours_stats, users_stats = stats.get_stats(
        project.id,
        current_app.config['GEO'])
    anon_pct_taskruns = int((users_stats['n_anon'] * 100) /
                            (users_stats['n_anon'] + users_stats['n_auth']))
    userStats = dict(
        geo=current_app.config['GEO'],
        anonymous=dict(
            users=users_stats['n_anon'],
            taskruns=users_stats['n_anon'],
            pct_taskruns=anon_pct_taskruns,
            top5=users_stats['anon']['top5']),
        authenticated=dict(
            users=users_stats['n_auth'],
            taskruns=users_stats['n_auth'],
            pct_taskruns=100 - anon_pct_taskruns,
            top5=users_stats['auth']['top5']))

    tmp = dict(userStats=users_stats['users'],
               userAnonStats=users_stats['anon'],
               userAuthStats=users_stats['auth'],
               dayStats=dates_stats,
               hourStats=hours_stats)

    return render_template('/projects/stats.html',
                           title=title,
                           projectStats=json.dumps(tmp),
                           userStats=userStats,
                           project=project)


@blueprint.route('/<short_name>/tasks/settings')
@login_required
def task_settings(short_name):
    """Settings page for tasks of the project"""
    project = project_by_shortname(short_name)
    try:
        require.project.read(project)
        require.project.update(project)
        return render_template('projects/task_settings.html',
                               project=project)
    except:
        return abort(403)


@blueprint.route('/<short_name>/tasks/redundancy', methods=['GET', 'POST'])
@login_required
def task_n_answers(short_name):
    project = project_by_shortname(short_name)
    title = project_title(project, lazy_gettext('Redundancy'))
    form = TaskRedundancyForm()
    try:
        require.project.read(project)
        require.project.update(project)
        if request.method == 'GET':
            return render_template('/projects/task_n_answers.html',
                                   title=title,
                                   form=form,
                                   project=project)
        elif request.method == 'POST' and form.validate():
            sql = text('''UPDATE task SET n_answers=:n_answers WHERE project_id=:project_id''')
            db.engine.execute(sql, n_answers=form.n_answers.data, project_id=project.id)
            msg = lazy_gettext('Redundancy of Tasks updated!')
            flash(msg, 'success')
            return redirect(url_for('.tasks', short_name=project.short_name))
        else:
            flash(lazy_gettext('Please correct the errors'), 'error')
            return render_template('/projects/task_n_answers.html',
                                   title=title,
                                   form=form,
                                   project=project)
    except:
        return abort(403)


@blueprint.route('/<short_name>/tasks/scheduler', methods=['GET', 'POST'])
@login_required
def task_scheduler(short_name):
    project = project_by_shortname(short_name)
    title = project_title(project, lazy_gettext('Scheduler'))
    form = TaskSchedulerForm()

    def respond():
        return render_template('/projects/task_scheduler.html',
                               title=title,
                               form=form,
                               project=project)
    try:
        require.project.read(project)
        require.project.update(project)
    except:
        return abort(403)

    if request.method == 'GET':
        if project.info.get('sched'):
            for s in form.sched.choices:
                if project.info['sched'] == s[0]:
                    form.sched.data = s[0]
                    break
        return respond()

    if request.method == 'POST' and form.validate():
        if form.sched.data:
            project.info['sched'] = form.sched.data
        cached_projects.reset()
        db.session.add(project)
        db.session.commit()
        msg = lazy_gettext("Project Task Scheduler updated!")
        flash(msg, 'success')
        return redirect(url_for('.tasks', short_name=project.short_name))

    flash(lazy_gettext('Please correct the errors'), 'error')
    return respond()
