# -*- coding: utf-8 -*-
from odoo import fields, models


class CompanyDocumentType(models.Model):
    """
     Model to store and manage company document types.
    """
    _name = 'company.document.type'
    _description = 'Company Document Type'
    _rec_name = 'document_type'

    document_type = fields.Char(string="Title", required=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        readonly=True
    )
