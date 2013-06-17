from base import model, db


class TestModel:
    @classmethod
    def setup_class(self):
        model.rebuild_db()

    def tearDown(self):
        db.session.remove()

    def test_all(self):
        """Test MODEL works"""
        username = u'test-user-1'
        user = model.User(name=username)
        info = {
            'total': 150,
            'long_description': 'hello world'}
        project = model.Project(
            name=u'My New App',
            short_name=u'my-new-project',
            info=info)
        project.owner = user
        task_info = {
            'question': 'My random question',
            'url': 'my url'}
        task = model.Task(info=task_info)
        task_run_info = {'answer': u'annakarenina'}
        task_run = model.TaskRun(info=task_run_info)
        task.project = project
        task_run.task = task
        task_run.user = user
        db.session.add_all([user, project, task, task_run])
        db.session.commit()
        project_id = project.id

        db.session.remove()

        project = db.session.query(model.Project).get(project_id)
        assert project.name == u'My New App', project
        # year would start with 201...
        assert project.created.startswith('201'), project.created
        assert project.long_tasks == 0, project.long_tasks
        assert project.hidden == 0, project.hidden
        assert project.time_estimate == 0, project
        assert project.time_limit == 0, project
        assert project.calibration_frac == 0, project
        assert project.bolt_course_id == 0
        assert len(project.tasks) == 1, project
        assert project.owner.name == username, project
        out_task = project.tasks[0]
        assert out_task.info['question'] == task_info['question'], out_task
        assert out_task.quorum == 0, out_task
        assert out_task.state == "ongoing", out_task
        assert out_task.calibration == 0, out_task
        assert out_task.priority_0 == 0, out_task
        assert len(out_task.task_runs) == 1, out_task
        outrun = out_task.task_runs[0]
        assert outrun.info['answer'] == task_run_info['answer'], outrun
        assert outrun.user.name == username, outrun

        user = model.User.by_name(username)
        assert user.projects[0].id == project_id, user

    def test_user(self):
        """Test MODEL User works"""
        user = model.User(name=u'test-user', email_addr=u'test@xyz.org')
        db.session.add(user)
        db.session.commit()

        db.session.remove()
        user = model.User.by_name(u'test-user')
        assert user, user
        assert len(user.api_key) == 36, user

        out = user.dictize()
        assert out['name'] == u'test-user', out
