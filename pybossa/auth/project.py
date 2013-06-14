from flaskext.login import current_user


def create(project=None):
    return not current_user.is_anonymous()


def read(project=None):
    return True


def update(project):
    if not current_user.is_anonymous() and (project.owner_id == current_user.id
                                            or current_user.admin is True):
        return True
    else:
        return False


def delete(project):
    return update(project)
