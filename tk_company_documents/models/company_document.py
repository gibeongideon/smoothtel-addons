# -*- coding: utf-8 -*-
from datetime import timedelta, date
from odoo import fields, models, api, _
from odoo.exceptions import UserError


class CompanyDocumentDetails(models.Model):
    """
     Stores company document details and sends notifications on expiration.

    Tracks documents' expiration dates and automatically notifies
    responsible users when documents are about to expire or have
    expired.
    """
    _name = 'company.document.details'
    _description = 'Company Document Details'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char(string="Title")
    document = fields.Binary(string="Document")
    document_name = fields.Char()
    issue_date = fields.Date(string="Issue Date")
    expiry_date = fields.Date(string="Expiry Date")
    document_type_id = fields.Many2one(
        'company.document.type',
        string="Document Type",
        required=True)
    note = fields.Html(string="Note")
    sequence = fields.Char(string="Sequence", default='New')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirm', 'Confirm'),
        ('expire', 'Expire'),
    ], default='draft')
    responsible_user_id = fields.Many2one(
        'res.users', string="Responsible", default=lambda self: self.env.user.id
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
    )

    @api.model_create_multi
    def create(self, values):
        """
        Create a company document and assign a unique sequence.
        """
        for vals in values:
            vals['sequence'] = self.env['ir.sequence'].next_by_code('company.document.details')
        return super().create(values)

    def action_document_confirm(self):
        """
        Set the document state to 'confirm'.
        """
        self.state = 'confirm'

    @api.constrains('issue_date', 'expiry_date')
    def _check_dates(self):
        """Validate the expiry issue dare and expiry  date."""
        for records in self:
            if records.issue_date > records.expiry_date:
                raise UserError("Expiry Date must be after Issue Date.")

    @api.model
    def check_company_document_expiry(self):
        """
         Check and update the expiration status of company documents.
         Send notification of expire documents.
        """
        config_expire_days = (self.env['ir.config_parameter']
                              .sudo().get_param('tk_company_documents.expire_days',
                                                default=2))
        today_date = date.today()
        target_date = today_date + timedelta(days=int(config_expire_days))
        all_documents = self.env['company.document.details'].search([
            ('state', '=', 'confirm'),
        ])
        for document in all_documents:
            if document.expiry_date <= today_date:
                document.state = 'expire'
        documents = self.env['company.document.details'].search([
            ('state', '=', 'confirm'),
            ('expiry_date', '=', target_date),
        ])
        template = self.env.ref('tk_company_documents.email_template_expiry_reminder')
        for doc in documents:
            template.send_mail(doc.id, force_send=True,
                               email_values={"author_id": doc.company_id.partner_id.id}, )
