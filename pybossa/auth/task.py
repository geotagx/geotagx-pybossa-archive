from flaskext.login import current_user
import pybossa.model as model
from pybossa.core import db


def create(task=None):
    if not current_user.is_anonymous():
        project = db.session.query(model.Project).filter_by(id=task.project_id).one()
        if project.owner_id == current_user.id or current_user.admin is True:
            return True
        else:
            return False
    else:
        return False


def read(task=None):
    return True


def update(task):
    if not current_user.is_anonymous():
        project = db.session.query(model.Project).filter_by(id=task.project_id).one()
        if project .owner_id == current_user.id or current_user.admin is True:
            return True
        else:
            return False
    else:
        return False


def delete(task):
    return update(task)
