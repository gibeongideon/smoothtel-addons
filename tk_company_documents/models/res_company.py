# -*- coding: utf-8 -*-
from odoo import models, fields


class ResCompany(models.Model):
    """
    Inherits res.company to manage related company documents via a One2many field.
    """
    _inherit = 'res.company'

    company_document_ids = fields.One2many(
        'company.document.details', 'company_id',
        string="Company Documents")
    documents_count = fields.Char(
        readonly=True,
        compute='_compute_count_documents'
    )

    def _compute_count_documents(self):
        """
        Count all company document records.

        Updates the 'documents_count' field with the total number
        of records found in the 'company.document.details' model.
        """
        for record in self:
            record.documents_count = record.env['company.document.details'].search_count([
                ('company_id', '=', record.id)
            ])

    def company_document_details_action(self):
        """
        Return an action to open the company document details list view.
        """
        return {
            'type': 'ir.actions.act_window',
            'name': 'Documents',
            'view_mode': 'list,form',
            'res_model': 'company.document.details',
            'domain':[('company_id', '=', self.id)],
        }
