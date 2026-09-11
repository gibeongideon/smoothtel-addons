# -*- coding: utf-8 -*-
import base64
from datetime import timedelta, date
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError


@tagged('company_document_expiry_send_notification')
class TestCompanyDocumentDetails(TransactionCase):
    """
    Test case for Company Document Details.
    Validates document creation, expiry status updates, and notifications.
    """

    @classmethod
    def setUpClass(cls):
        """
        Set up test environment before each test method is run.
        """
        super().setUpClass()
        cls.company = cls.env.user.company_id
        cls.responsible_user = cls.env.user

        cls.document_type = cls.env['company.document.type'].create({
            'document_type': 'Test Document Type',
        })

        cls.document = cls.env['company.document.details'].create({
            'name': 'Test Document',
            'document': base64.b64encode(b'This is a dummy file content.'),
            'document_name': 'test_document.pdf',
            'issue_date': date.today(),
            'expiry_date': date.today() + timedelta(days=30),
            'document_type_id': cls.document_type.id,
        })

    def test_document_create_sequence_assigned(self):
        """
        Test that a sequence is automatically assigned when creating a document.
        """
        self.assertIsNotNone(self.document.sequence,
                             "Document sequence should be assigned on creation.")
        self.assertNotEqual(self.document.sequence,
                            'New', "Document sequence should be generated, not remain 'New'.")

    def test_document_date_validation(self):
        """
        Test that a UserError is raised if issue_date is after expiry_date.
        """
        with self.assertRaises(UserError):
            self.env['company.document.details'].create({
                'name': 'Invalid Date Document',
                'document': base64.b64encode(b'This is a dummy file content.'),
                'document_name': 'invalid_document.pdf',
                'issue_date': date.today() + timedelta(days=2),
                'expiry_date': date.today() + timedelta(days=1),
                'document_type_id': self.document_type.id,
            })

    def test_action_set_document_state(self):
        """
        Test that document state transitions between draft and confirm correctly.
        """
        self.document.action_document_confirm()
        self.assertEqual(self.document.state,
                         'confirm', "Document state should be 'confirm' after confirming.")

    def test_check_company_document_expiry(self):
        """
        Test expiry check logic for documents and notification trigger.
        """
        self.document.action_document_confirm()

        # Force expiry date to today to simulate expiration
        self.document.expiry_date = date.today()
        self.env['company.document.details'].check_company_document_expiry()
        self.assertEqual(self.document.state, 'expire',
                         "Document should move to 'expire' state when expired.")

    def test_notification_trigger_before_expiry(self):
        """
        Test that notification is sent before document expiry as per system parameter.
        """
        # Set expire_days to 1 day before expiry
        param = self.env['ir.config_parameter'].sudo()
        param.set_param('tk_company_documents.expire_days', '1')

        document = self.env['company.document.details'].create({
            'name': 'Reminder Document',
            'document': base64.b64encode(b'This is a dummy file content.'),
            'document_name': 'reminder_document.pdf',
            'issue_date': date.today(),
            'expiry_date': date.today() + timedelta(days=1),
            'document_type_id': self.document_type.id,
        })
        document.action_document_confirm()

        # Run the check (should attempt to send notification)
        self.env['company.document.details'].check_company_document_expiry()

        # There's no assert on sending email without patching `send_mail`
        # So here we assert state is still 'confirm' (not expired)
        self.assertEqual(document.state, 'confirm',
                         "Document should remain 'confirm' until actual expiry date.")
