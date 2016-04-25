# -*- coding: utf-8 -*-
import httplib as http
import mock
import unittest  # noqa
from nose.tools import *  # noqa (PEP8 asserts)

import datetime
from modularodm import fields, storage, Q

from tests.base import OsfTestCase
from tests import factories
from tests.utils import mock_archive, assert_logs

from framework.auth import Auth
from framework.mongo import handlers

from website.exceptions import NodeStateError
from website.project.model import ensure_schemas, Node, NodeLog
from website.project.sanctions import Sanction, TokenApprovableSanction, EmailApprovableSanction, PreregCallbackMixin

def valid_user():
    return factories.UserFactory(system_tags=['flag'])

class SanctionTestClass(TokenApprovableSanction):

    DISPLAY_NAME = 'test class'

    initiated_by = fields.ForeignField('user', backref='tested')

    def _validate_authorizer(self, user):
        return 'flag' in user.system_tags

    def _get_registration(self):
        return factories.RegistrationFactory()

class EmailApprovableSanctionTestClass(PreregCallbackMixin, EmailApprovableSanction):

    AUTHORIZER_NOTIFY_EMAIL_TEMPLATE = 'authorizer'
    NON_AUTHORIZER_NOTIFY_EMAIL_TEMPLATE = 'non-authorizer'

    def _get_registration(self):
        return factories.RegistrationFactory()


class SanctionsTestCase(OsfTestCase):

    def setUp(self, *args, **kwargs):
        super(SanctionsTestCase, self).setUp(*args, **kwargs)
        handlers.set_up_storage([
            SanctionTestClass,
            EmailApprovableSanctionTestClass
        ], storage.MongoStorage)

class TestSanction(SanctionsTestCase):

    def setUp(self, *args, **kwargs):
        super(TestSanction, self).setUp(*args, **kwargs)
        self.user = valid_user()
        self.invalid_user = factories.UserFactory()
        self.sanction = SanctionTestClass(
            initiated_by=self.user,
            end_date=datetime.datetime.now() + datetime.timedelta(days=2)
        )
        self.registration = factories.RegistrationFactory()
        self.sanction.add_authorizer(self.user, self.registration, save=True)

    def test_pending_approval(self):
        assert_true(self.sanction.is_pending_approval)
        self.sanction.state = Sanction.APPROVED
        assert_false(self.sanction.is_pending_approval)

    def test_validate_authorizer(self):
        assert_false(self.sanction._validate_authorizer(self.invalid_user))
        assert_true(self.sanction._validate_authorizer(self.user))

    def test_add_authorizer(self):
        new_user = valid_user()
        added = self.sanction.add_authorizer(new_user, node=self.registration)
        assert_true(added)
        assert_in(new_user._id, self.sanction.approval_state.keys())
        assert_in('approval_token', self.sanction.approval_state[new_user._id])
        assert_in('rejection_token', self.sanction.approval_state[new_user._id])
        assert_equal(self.sanction.approval_state[new_user._id]['node_id'], self.registration._id)

    def test_add_authorizer_already_added(self):
        added = self.sanction.add_authorizer(self.user, self.registration)
        assert_false(added)
        assert_in(self.user._id, self.sanction.approval_state.keys())

    def test_add_authorizer_invalid(self):
        invalid_user = factories.UserFactory()
        added = self.sanction.add_authorizer(invalid_user, self.registration)
        assert_false(added)
        assert_not_in(invalid_user._id, self.sanction.approval_state.keys())

    def test_remove_authorizer(self):
        removed = self.sanction.remove_authorizer(self.user)
        self.sanction.save()
        assert_true(removed)
        assert_not_in(self.user._id, self.sanction.approval_state.keys())

    def test_remove_authorizer_not_added(self):
        not_added = factories.UserFactory()
        removed = self.sanction.remove_authorizer(not_added)
        self.sanction.save()
        assert_false(removed)
        assert_not_in(not_added, self.sanction.approval_state.keys())

    @mock.patch.object(SanctionTestClass, '_on_complete')
    def test_on_approve_incomplete(self, mock_complete):
        another_user = valid_user()
        self.sanction.add_authorizer(another_user, self.sanction._get_registration(), approved=True)
        self.sanction._on_approve(self.user, '')
        assert_false(mock_complete.called)

    @mock.patch.object(SanctionTestClass, '_on_complete')
    def test_on_approve_complete(self, mock_complete):
        self.sanction.approval_state[self.user._id]['has_approved'] = True
        self.sanction._on_approve(self.user, '')
        assert_true(mock_complete.called)

    def test_on_reject_raises_NotImplementedError(self):
        err = lambda: self.sanction._on_reject(self.user)
        assert_raises(NotImplementedError, err)

    def test_on_complete_raises_NotImplementedError(self):
        err = lambda: self.sanction._on_complete(self.user)
        assert_raises(NotImplementedError, err)

    @mock.patch.object(SanctionTestClass, '_on_approve')
    def test_approve(self, mock_on_approve):
        approval_token = self.sanction.approval_state[self.user._id]['approval_token']
        self.sanction.approve(self.user, approval_token)
        assert_true(self.sanction.approval_state[self.user._id]['has_approved'])
        assert_true(mock_on_approve.called)

    @mock.patch.object(SanctionTestClass, '_on_reject')
    def test_reject(self, mock_on_reject):
        rejection_token = self.sanction.approval_state[self.user._id]['rejection_token']
        self.sanction.reject(self.user, rejection_token)
        assert_false(self.sanction.approval_state[self.user._id]['has_approved'])
        assert_true(mock_on_reject.called)

    @mock.patch.object(SanctionTestClass, '_notify_authorizer')
    @mock.patch.object(SanctionTestClass, '_notify_non_authorizer')
    def test_ask(self, mock_notify_non_authorizer, mock_notify_authorizer):
        other_user = factories.UserFactory()
        p1 = factories.ProjectFactory()
        p2 = factories.ProjectFactory()
        group = [
            (other_user, p1),
            (self.user, p2),
        ]
        self.sanction.ask(group)
        mock_notify_non_authorizer.assert_called_once_with(other_user, p1)
        mock_notify_authorizer.assert_called_once_with(self.user, p2)


class TestEmailApprovableSanction(SanctionsTestCase):

    def setUp(self, *args, **kwargs):
        super(TestEmailApprovableSanction, self).setUp(*args, **kwargs)
        self.user = factories.UserFactory()
        self.sanction = EmailApprovableSanctionTestClass(
            initiated_by=self.user,
            end_date=datetime.datetime.now() + datetime.timedelta(days=2)
        )
        self.sanction.add_authorizer(self.user, self.sanction._get_registration())

    def test_format_or_empty(self):
        context = {
            'key': 'value'
        }
        template = 'What a good {key}'
        assert_equal(EmailApprovableSanctionTestClass._format_or_empty(template, context), 'What a good value')

    def test_format_or_empty_empty(self):
        context = None
        template = 'What a good {key}'
        assert_equal(EmailApprovableSanctionTestClass._format_or_empty(template, context), '')

    @mock.patch.object(EmailApprovableSanctionTestClass, '_send_approval_request_email')
    @mock.patch.object(EmailApprovableSanctionTestClass, '_email_template_context')
    def test_notify_authorizer(self, mock_get_email_template_context, mock_send_approval_email):
        mock_get_email_template_context.return_value = 'context'
        reg  = self.sanction._get_registration()
        self.sanction._notify_authorizer(self.user, reg)
        mock_get_email_template_context.assert_called_once_with(
            self.user,
            reg, 
            is_authorizer=True
        )
        mock_send_approval_email.assert_called_once_with(self.user, 'authorizer', 'context')

    @mock.patch.object(EmailApprovableSanctionTestClass, '_send_approval_request_email')
    @mock.patch.object(EmailApprovableSanctionTestClass, '_email_template_context')
    def test_notify_non_authorizer(self, mock_get_email_template_context, mock_send_approval_email):
        mock_get_email_template_context.return_value = 'context'
        other_user = factories.UserFactory()
        reg = self.sanction._get_registration()
        self.sanction._notify_non_authorizer(other_user, reg)
        mock_get_email_template_context.assert_called_once_with(
            other_user,
            reg
        )
        mock_send_approval_email.assert_called_once_with(other_user, 'non-authorizer', 'context')

    def test_add_authorizer(self):
        assert_is_not_none(self.sanction.stashed_urls.get(self.user._id))

    @mock.patch('website.mails.send_mail')
    def test__notify_authorizer(self, mock_send):
        self.sanction._notify_authorizer(self.user, self.sanction._get_registration())
        assert_true(mock_send.called)
        args, kwargs = mock_send.call_args
        assert_true(self.user.username in args)

    @mock.patch('website.mails.send_mail')
    def test__notify_non_authorizer(self, mock_send):
        self.sanction._notify_non_authorizer(self.user, self.sanction._get_registration())
        assert_true(mock_send.called)
        args, kwargs = mock_send.call_args
        assert_true(self.user.username in args)

    @mock.patch('website.mails.send_mail')
    def test_ask(self, mock_send):
        group = [(self.user, factories.ProjectFactory())]
        for i in range(5):
            u, n = factories.UserFactory(), factories.ProjectFactory()
            group.append((u, n))
        self.sanction.ask(group)
        authorizer = group.pop(0)[0]
        mock_send.assert_any_call(
            authorizer.username,
            self.sanction.AUTHORIZER_NOTIFY_EMAIL_TEMPLATE,
            user=authorizer,
            **{}
        )
        for user, _ in group:
            mock_send.assert_any_call(
                user.username,
                self.sanction.NON_AUTHORIZER_NOTIFY_EMAIL_TEMPLATE,
                user=user,
                **{}
            )

    def test_on_complete_notify_initiator(self):
        sanction = EmailApprovableSanctionTestClass(
            initiated_by=self.user,
            end_date=datetime.datetime.now() + datetime.timedelta(days=2),
            notify_initiator_on_complete=True
        )
        sanction.add_authorizer(self.user, sanction._get_registration())
        sanction.save()
        with mock.patch.object(EmailApprovableSanctionTestClass, '_notify_initiator') as mock_notify:
            sanction._on_complete(self.user)
        assert_equal(mock_notify.call_count, 1)

    def test_notify_initiator_with_PreregCallbackMixin(self):
        sanction = EmailApprovableSanctionTestClass(
            initiated_by=self.user,
            end_date=datetime.datetime.now() + datetime.timedelta(days=2),
            notify_initiator_on_complete=True
        )
        sanction.add_authorizer(self.user, sanction._get_registration())
        sanction.save()
        with mock.patch.object(PreregCallbackMixin, '_notify_initiator') as mock_notify:
            sanction._on_complete(self.user)
        assert_equal(mock_notify.call_count, 1)


class TestRegistrationApproval(OsfTestCase):

    def setUp(self):
        super(TestRegistrationApproval, self).setUp()
        ensure_schemas()
        self.user = factories.AuthUserFactory()
        self.registration = factories.RegistrationFactory(creator=self.user, archive=True)

    @mock.patch('framework.celery_tasks.handlers.enqueue_task')
    def test_non_contributor_GET_approval_returns_HTTPError(self, mock_enqueue):
        non_contributor = factories.AuthUserFactory()

        approval_token = self.registration.registration_approval.approval_state[self.user._id]['approval_token']
        approval_url = self.registration.web_url_for('view_project', token=approval_token)

        res = self.app.get(approval_url, auth=non_contributor.auth, expect_errors=True)
        assert_equal(http.FORBIDDEN, res.status_code)
        assert_true(self.registration.is_pending_registration)
        assert_false(self.registration.is_registration_approved)

    @mock.patch('framework.celery_tasks.handlers.enqueue_task')
    def test_non_contributor_GET_disapproval_returns_HTTPError(self, mock_enqueue):
        non_contributor = factories.AuthUserFactory()

        rejection_token = self.registration.registration_approval.approval_state[self.user._id]['rejection_token']
        rejection_url = self.registration.web_url_for('view_project', token=rejection_token)

        res = self.app.get(rejection_url, auth=non_contributor.auth, expect_errors=True)
        assert_equal(http.FORBIDDEN, res.status_code)
        assert_true(self.registration.is_pending_registration)
        assert_false(self.registration.is_registration_approved)


class TestRegistrationApprovalHooks(OsfTestCase):

    # Regression test for https://openscience.atlassian.net/browse/OSF-4940
    def test_on_complete_sets_state_to_approved(self):
        user = factories.UserFactory()
        registration = factories.RegistrationFactory(creator=user)
        registration.require_approval(user)

        assert_true(registration.registration_approval.is_pending_approval)  # sanity check
        registration.registration_approval._on_complete(None)
        assert_false(registration.registration_approval.is_pending_approval)

class TestNodeSanctionStates(OsfTestCase):

    def test_sanction_none(self):
        node = factories.NodeFactory()
        assert_false(node.sanction)

    def test_sanction_embargo_termination_first(self):
        embargo_termination_approval = factories.EmbargoTerminationApprovalFactory()
        registration = Node.find_one(Q('embargo_termination_approval', 'eq', embargo_termination_approval))
        assert_equal(registration.sanction, embargo_termination_approval)

    def test_sanction_retraction(self):
        retraction = factories.RetractionFactory()
        registration = Node.find_one(Q('retraction', 'eq', retraction))
        assert_equal(registration.sanction, retraction)

    def test_sanction_embargo(self):
        embargo = factories.EmbargoFactory()
        registration = Node.find_one(Q('embargo', 'eq', embargo))
        assert_equal(registration.sanction, embargo)

    def test_sanction_registration_approval(self):
        registration_approval = factories.RegistrationApprovalFactory()
        registration = Node.find_one(Q('registration_approval', 'eq', registration_approval))
        assert_equal(registration.sanction, registration_approval)

    def test_sanction_searches_parents(self):
        user = factories.AuthUserFactory()
        node = factories.NodeFactory(creator=user)
        child = factories.NodeFactory(creator=user, parent=node)
        factories.NodeFactory(creator=user, parent=child)
        with mock_archive(node) as registration:
            approval = registration.registration_approval
            sub_reg = registration.nodes[0].nodes[0]
            assert_equal(sub_reg.sanction, approval)

    def test_is_pending_registration(self):
        registration_approval = factories.RegistrationApprovalFactory()
        registration = Node.find_one(Q('registration_approval', 'eq', registration_approval))
        assert_true(registration_approval.is_pending_approval)
        assert_true(registration.is_pending_registration)

    def test_is_pending_registration_searches_parents(self):
        user = factories.AuthUserFactory()
        node = factories.NodeFactory(creator=user)
        child = factories.NodeFactory(creator=user, parent=node)
        factories.NodeFactory(creator=user, parent=child)
        with mock_archive(node) as registration:
            sub_reg = registration.nodes[0].nodes[0]
            assert_true(sub_reg.is_pending_registration)

    def test_is_registration_approved(self):
        registration_approval = factories.RegistrationApprovalFactory()
        registration = Node.find_one(Q('registration_approval', 'eq', registration_approval))
        with mock.patch('website.project.sanctions.Sanction.is_approved', mock.Mock(return_value=True)):
            assert_true(registration.is_registration_approved)

    def test_is_registration_approved_searches_parents(self):
        user = factories.AuthUserFactory()
        node = factories.NodeFactory(creator=user)
        child = factories.NodeFactory(creator=user, parent=node)
        factories.NodeFactory(creator=user, parent=child)
        with mock_archive(node) as registration:
            with mock.patch('website.project.sanctions.Sanction.is_approved', mock.Mock(return_value=True)):
                sub_reg = registration.nodes[0].nodes[0]
                assert_true(sub_reg.is_registration_approved)

    def test_is_retracted(self):
        retraction = factories.RetractionFactory()
        registration = Node.find_one(Q('retraction', 'eq', retraction))
        with mock.patch('website.project.sanctions.Sanction.is_approved', mock.Mock(return_value=True)):
            assert_true(registration.is_retracted)

    def test_is_retracted_searches_parents(self):
        user = factories.AuthUserFactory()
        node = factories.NodeFactory(creator=user)
        child = factories.NodeFactory(creator=user, parent=node)
        factories.NodeFactory(creator=user, parent=child)
        with mock_archive(node, autoapprove=True, retraction=True, autoapprove_retraction=True) as registration:
            sub_reg = registration.nodes[0].nodes[0]
            assert_true(sub_reg.is_retracted)

    def test_is_pending_retraction(self):
        retraction = factories.RetractionFactory()
        registration = Node.find_one(Q('retraction', 'eq', retraction))
        assert_true(retraction.is_pending_approval)
        assert_true(registration.is_pending_retraction)

    def test_is_pending_retraction_searches_parents(self):
        user = factories.AuthUserFactory()
        node = factories.NodeFactory(creator=user)
        child = factories.NodeFactory(creator=user, parent=node)
        factories.NodeFactory(creator=user, parent=child)
        with mock_archive(node, autoapprove=True, retraction=True) as registration:
            sub_reg = registration.nodes[0].nodes[0]
            assert_true(sub_reg.is_pending_retraction)

    def test_embargo_end_date(self):
        embargo = factories.EmbargoFactory()
        registration = Node.find_one(Q('embargo', 'eq', embargo))
        assert_equal(registration.embargo_end_date, embargo.end_date)

    def test_embargo_end_date_searches_parents(self):
        user = factories.AuthUserFactory()
        node = factories.NodeFactory(creator=user)
        child = factories.NodeFactory(creator=user, parent=node)
        factories.NodeFactory(creator=user, parent=child)
        with mock_archive(node, embargo=True) as registration:
            sub_reg = registration.nodes[0].nodes[0]
            assert_equal(sub_reg.embargo_end_date, registration.embargo_end_date)

    def test_is_pending_embargo(self):
        embargo = factories.EmbargoFactory()
        registration = Node.find_one(Q('embargo', 'eq', embargo))
        assert_true(embargo.is_pending_approval)
        assert_true(registration.is_pending_embargo)

    def test_is_pending_embargo_searches_parents(self):
        user = factories.AuthUserFactory()
        node = factories.NodeFactory(creator=user)
        child = factories.NodeFactory(creator=user, parent=node)
        factories.NodeFactory(creator=user, parent=child)
        with mock_archive(node, embargo=True) as registration:
            sub_reg = registration.nodes[0].nodes[0]
            assert_true(sub_reg.is_pending_embargo)

    def test_is_embargoed(self):
        embargo = factories.EmbargoFactory()
        registration = Node.find_one(Q('embargo', 'eq', embargo))
        with mock.patch('website.project.sanctions.Sanction.is_approved', mock.Mock(return_value=True)):
            assert_true(registration.is_embargoed)

    def test_is_embargoed_searches_parents(self):
        user = factories.AuthUserFactory()
        node = factories.NodeFactory(creator=user)
        child = factories.NodeFactory(creator=user, parent=node)
        factories.NodeFactory(creator=user, parent=child)
        with mock_archive(node, embargo=True, autoapprove=True) as registration:
            sub_reg = registration.nodes[0].nodes[0]
            assert_true(sub_reg.is_embargoed)

class TestNodeEmbargoTerminations(OsfTestCase):

    def tearDown(self):
        with mock.patch('framework.celery_tasks.handlers.queue', mock.Mock(return_value=None)):
            super(TestNodeEmbargoTerminations, self).tearDown()

    def setUp(self):
        super(TestNodeEmbargoTerminations, self).setUp()

        self.user = factories.AuthUserFactory()
        self.node = factories.ProjectFactory(creator=self.user)
        with mock_archive(self.node, embargo=True, autoapprove=True) as registration:
            self.registration = registration

        self.not_embargoed = factories.RegistrationFactory()

    def test_request_embargo_termination_not_embargoed(self):
        with assert_raises(NodeStateError):
            self.not_embargoed.request_embargo_termination(Auth(self.user))

    def test_terminate_embargo_makes_registrations_public(self):
        self.registration.terminate_embargo(Auth(self.user))
        for node in self.registration.node_and_primary_descendants():
            assert_true(node.is_public)
            assert_false(node.is_embargoed)

    @assert_logs(NodeLog.EMBARGO_TERMINATED, 'node')
    def test_terminate_embargo_adds_log_to_registered_from(self):
        self.registration.terminate_embargo(Auth(self.user))

    def test_terminate_embargo_log_is_nouser(self):
        self.registration.terminate_embargo(Auth(self.user))
        last_log = self.node.logs[-1]
        assert_equal(last_log.action, NodeLog.EMBARGO_TERMINATED)
        assert_equal(last_log.user, None)
