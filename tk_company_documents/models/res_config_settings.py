# -*- coding: utf-8 -*-
from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    """
    Adds a configuration setting field `expire_days` to allow users to define the number of days
    after which a specific document should be considered expired.
    """
    _inherit = 'res.config.settings'

    expire_days = fields.Integer(
        string="Document Expire Before Days",
        config_parameter='tk_company_documents.expire_days',
        default=2,
    )
