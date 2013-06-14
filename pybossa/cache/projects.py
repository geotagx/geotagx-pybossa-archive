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
from sqlalchemy.sql import func, text
from pybossa.core import cache
from pybossa.core import db
from pybossa.model import Featured, Project, TaskRun, Task
from pybossa.util import pretty_date

import json
import string
import operator
import datetime
import time
from datetime import timedelta

STATS_TIMEOUT=50

@cache.cached(key_prefix="front_page_featured_projects")
def get_featured_front_page():
    """Return featured projects"""
    sql = text('''SELECT project.id, project.name, project.short_name, project.info FROM
               project, featured where project.id=featured.project_id and project.hidden=0''')
    results = db.engine.execute(sql)
    featured = []
    for row in results:
        project = dict(id=row.id, name=row.name, short_name=row.short_name,
                   info=dict(json.loads(row.info)))
        featured.append(project)
    return featured


@cache.cached(key_prefix="front_page_top_projects")
def get_top(n=4):
    """Return top n=4 projects"""
    sql = text('''
    SELECT project.id, project.name, project.short_name, project.description, project.info,
    count(project_id) AS total FROM task_run, project WHERE project_id IS NOT NULL AND
    project.id=project_id AND project.hidden=0 GROUP BY project.id ORDER BY total DESC LIMIT :limit;
    ''')

    results = db.engine.execute(sql, limit=n)
    top_projects = []
    for row in results:
        project = dict(name=row.name, short_name=row.short_name,
                   description=row.description,
                   info=json.loads(row.info))
        top_projects.append(project)
    return top_projects


@cache.memoize(timeout=60*5)
def last_activity(project_id):
    sql = text('''SELECT finish_time FROM task_run WHERE project_id=:project_id
               ORDER BY finish_time DESC LIMIT 1''')
    results = db.engine.execute(sql, project_id=project_id)
    for row in results:
        if row is not None:
            print pretty_date(row[0])
            return pretty_date(row[0])
        else:
            return None

@cache.memoize()
def overall_progress(project_id):
    sql = text('''SELECT COUNT(task_id) FROM task_run WHERE project_id=:project_id''')
    results = db.engine.execute(sql, project_id=project_id)
    for row in results:
        n_task_runs = float(row[0])
    sql = text('''SELECT SUM(n_answers) FROM task WHERE project_id=:project_id''')
    results = db.engine.execute(sql, project_id=project_id)
    for row in results:
        if row[0] is None:
            n_expected_task_runs = float(30 * n_task_runs)
        else:
            n_expected_task_runs = float(row[0])
    pct = float(0)
    if n_expected_task_runs != 0:
        pct = n_task_runs / n_expected_task_runs
    return pct*100


@cache.memoize()
def last_activity(project_id):
    sql = text('''SELECT finish_time FROM task_run WHERE project_id=:project_id
               ORDER BY finish_time DESC LIMIT 1''')
    results = db.engine.execute(sql, project_id=project_id)
    for row in results:
        if row is not None:
            return pretty_date(row[0])
        else:
            return None

@cache.cached(key_prefix="number_featured_projects")
def n_featured():
    """Return number of featured projects"""
    sql = text('''select count(*) from featured;''')
    results = db.engine.execute(sql)
    for row in results:
        count = row[0]
    return count

@cache.memoize(timeout=50)
def get_featured(category, page=1, per_page=5):
    """Return a list of featured projects with a pagination"""

    count = n_featured()

    sql = text('''SELECT project.id, project.name, project.short_name, project.info, project.created,
               project.description,
               "user".fullname AS owner FROM project, featured, "user"
               WHERE project.id=featured.project_id AND project.hidden=0
               AND "user".id=project.owner_id GROUP BY project.id, "user".id
               OFFSET(:offset) LIMIT(:limit);
               ''')
    offset = (page - 1) * per_page
    results = db.engine.execute(sql, limit=per_page, offset=offset)
    projects = []
    for row in results:
        project = dict(id=row.id, name=row.name, short_name=row.short_name,
                   created=row.created, description=row.description,
                   overall_progress=overall_progress(row.id),
                   last_activity=last_activity(row.id),
                   owner=row.owner,
                   featured=row.id,
                   info=dict(json.loads(row.info)))
        projects.append(project)
    return projects, count

@cache.cached(key_prefix="number_published_projects")
def n_published():
    """Return number of published projects"""
    sql = text('''
               WITH published_projects as
               (SELECT project.id FROM project, task WHERE
               project.id=task.project_id AND project.hidden=0 AND project.info
               LIKE('%task_presenter%') GROUP BY project.id)
               SELECT COUNT(id) FROM published_projects;
               ''')
    results = db.engine.execute(sql)
    for row in results:
        count = row[0]
    return count

@cache.memoize(timeout=50)
def get_published(category, page=1, per_page=5):
    """Return a list of projects with a pagination"""

    count = n_published()

    sql = text('''
               SELECT project.id, project.name, project.short_name, project.description,
               project.info, project.created, "user".fullname AS owner,
               featured.project_id as featured
               FROM task, "user", project LEFT OUTER JOIN featured ON project.id=featured.project_id
               WHERE
               project.id=task.project_id AND project.info LIKE('%task_presenter%')
               AND project.hidden=0
               AND "user".id=project.owner_id
               GROUP BY project.id, "user".id, featured.id ORDER BY project.name
               OFFSET :offset
               LIMIT :limit;''')

    offset = (page - 1) * per_page
    results = db.engine.execute(sql, limit=per_page, offset=offset)
    projects = []
    for row in results:
        project = dict(id=row.id,
                   name=row.name, short_name=row.short_name,
                   created=row.created,
                   description=row.description,
                   owner=row.owner,
                   featured=row.featured,
                   last_activity=last_activity(row.id),
                   overall_progress=overall_progress(row.id),
                   info=dict(json.loads(row.info)))
        projects.append(project)
    return projects, count

@cache.cached(key_prefix="number_draft_projects")
def n_draft():
    """Return number of draft projects"""
    sql = text('''
               SELECT count(project.id) FROM project
               LEFT JOIN task on project.id=task.project_id
               WHERE task.project_id IS NULL AND project.info NOT LIKE('%task_presenter%')
               AND project.hidden=0;''')

    results = db.engine.execute(sql)
    for row in results:
        count = row[0]
    return count

@cache.memoize(timeout=50)
def get_draft(category, page=1, per_page=5):
    """Return list of draft projects"""

    count = n_draft()

    sql = text('''
               SELECT project.id, project.name, project.short_name, project.created,
               project.description, project.info, "user".fullname as owner
               FROM "user", project LEFT JOIN task ON project.id=task.project_id
               WHERE task.project_id IS NULL AND project.info NOT LIKE('%task_presenter%')
               AND project.hidden=0
               AND project.owner_id="user".id
               OFFSET :offset
               LIMIT :limit;''')

    offset = (page - 1) * per_page
    results = db.engine.execute(sql, limit=per_page, offset=offset)
    projects = []
    for row in results:
        project = dict(id=row.id, name=row.name, short_name=row.short_name,
                   created=row.created,
                   description=row.description,
                   owner=row.owner,
                   last_activity=last_activity(row.id),
                   overall_progress=overall_progress(row.id),
                   info=dict(json.loads(row.info)))
        projects.append(project)
    return projects, count


@cache.memoize(timeout=50)
def n_count(category):
    """Count the number of projects in a given category"""
    sql = text('''
               WITH uniq AS (
               SELECT COUNT(project.id) FROM task, project
               LEFT OUTER JOIN category ON project.category_id=category.id
               WHERE
               category.short_name=:category
               AND project.hidden=0
               AND project.info LIKE('%task_presenter%')
               AND task.project_id=project.id
               GROUP BY project.id)
               SELECT COUNT(*) FROM uniq
               ''')

    results = db.engine.execute(sql, category=category)
    count = 0
    for row in results:
        count = row[0]
    return count


@cache.memoize(timeout=50)
def get(category, page=1, per_page=5):
    """Return a list of projects with at least one task and a task_presenter
       with a pagination for a given category"""

    count = n_count(category)

    sql = text('''
               SELECT project.id, project.name, project.short_name, project.description,
               project.info, project.created, project.category_id, "user".fullname AS owner,
               featured.project_id as featured
               FROM "user", task, project
               LEFT OUTER JOIN category ON project.category_id=category.id
               LEFT OUTER JOIN featured ON project.id=featured.project_id
               WHERE
               category.short_name=:category
               AND project.hidden=0
               AND "user".id=project.owner_id
               AND project.info LIKE('%task_presenter%')
               AND task.project_id=project.id
               GROUP BY project.id, "user".id, featured.project_id ORDER BY project.name
               OFFSET :offset
               LIMIT :limit;''')

    offset = (page - 1) * per_page
    results = db.engine.execute(sql, category=category, limit=per_page, offset=offset)
    projects = []
    for row in results:
        project = dict(id=row.id,
                   name=row.name, short_name=row.short_name,
                   created=row.created,
                   description=row.description,
                   owner=row.owner,
                   featured=row.featured,
                   last_activity=last_activity(row.id),
                   overall_progress=overall_progress(row.id),
                   info=dict(json.loads(row.info)))
        projects.append(project)
    return projects, count


def reset():
    """Clean the cache"""
    cache.delete('front_page_featured_projects')
    cache.delete('front_page_top_projects')
    cache.delete('number_featured_projects')
    cache.delete('number_published_projects')
    cache.delete('number_draft_projects')
    cache.delete_memoized(get_published)
    cache.delete_memoized(get_featured)
    cache.delete_memoized(get_draft)
    cache.delete_memoized(n_count)
    cache.delete_memoized(get)


def clean(project_id):
    """Clean all items in cache"""
    reset()
    cache.delete_memoized(last_activity, project_id)
    cache.delete_memoized(overall_progress, project_id)
