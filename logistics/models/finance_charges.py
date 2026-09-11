# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, date

today = date.today()

class FinanceCharges(models.Model):
    """
    Model to manage the Finance Charges.
    """
    _name = 'finance.charges'
    _description = 'Finance Charges'
    _inherit = ['mail.thread', 'mail.activity.mixin'] 
    
    
    @api.model
    def create(self, vals):
        if vals.get("name", _("New")) == _("New"):
            vals["name"] = self.env["ir.sequence"].next_by_code("finance.charges") or _("New")
        res = super(FinanceCharges, self).create(vals)
        return res
    
    
    name = fields.Char(string='Finance File', required=True, copy=False, readonly=True,
                       index=True, default=lambda self: _('New')) 
    finance_state = fields.Selection(
    related='register_finance_file_id.state',
    string='Register State',
    readonly=True,
    store=True
    )
    inv_ref = fields.Char(readonly=True, tracking=True, string="Invoice Ref")
    register_finance_file_id = fields.Many2one('register.file', string="Register File", ondelete='cascade', readonly=True)
    shipping_finance_file_id = fields.Many2one('shipping.file', string="Shipping File", ondelete='cascade', readonly=True)
    account_total = fields.Float(
        string="Total Amount", tracking=True, compute="calculate_account_blc"
    )
    # account_status = fields.Many2one("account.move", string="Account Status", required=True)
    # invoice_status = fields.Selection(
    # related='account_status.status_in_payment',
    # string='Invoice Status',
    # readonly=True,
    # store=True
    # )
    invoice_count = fields.Integer(compute="compute_count")
    finance_lines = fields.One2many("finance.charges.line", "assoc_finance_line")
    create_date = fields.Datetime(string='Date Created', tracking=True)
    operator_id = fields.Many2one('res.users', 'Created by', default=lambda self: self.env.user, readonly=True)
    client = fields.Many2one(related='register_finance_file_id.consignee_name', store=True, string='Customer')
    journal_id = fields.Many2one("account.journal", string="Journal", required=True)
    invoice_payment_term_id = fields.Many2one("account.payment.term", required=True)
    inv_ref = fields.Char(readonly=True, tracking=True, string="Invoice Ref")
    
    
    def create_invoice(self):
        inv_lines = [
            (
                0,
                0,
                {
                    "product_id": x.product_item.id,
                    "name": x.name_id,
                    "account_id": x.account_id.id,
                },
            )
            for x in self.finance_lines
        ]

        invoice = self.env["account.move"].sudo().create({
            "partner_id": self.client.id,
            "invoice_date": self.create_date,
            "move_type": "out_invoice",
            "invoice_payment_term_id": self.invoice_payment_term_id.id,
            "journal_id": self.journal_id.id,
            "file_ref": self.name,
            "invoice_line_ids": inv_lines,
        })

        # ✅ Post the invoice to generate the invoice number (e.g., INV/2025/00002)
        invoice.action_post()

        # ✅ Store the posted invoice's name in inv_ref
        self.write({
            "inv_ref": invoice.name,
            # optionally update the state
            "finance_state": "invoiced"
        })

        return True
    
    
    def get_associated_invoice(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Invoices",
            "view_mode": "list,form",
            "res_model": "account.move",
            "domain": [("file_ref", "=", self.name)],
            "context": "{'create': False}",
        }

    
    def compute_count(self):
        unpaid = 0.00
        invoices = self.env["account.move"].search([("file_ref", "=", self.name)])
        for record in invoices:
            unpaid += record.amount_residual
        return self.sudo().write({"invoice_count": unpaid})

    def action_finance_register_file(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'register.file',
            'view_mode': 'form',
            'res_id': self.register_finance_file_id.id,
            'target': 'current',
        }
        
    def action_finance_shipping_file(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'shipping.file',
            'view_mode': 'form',
            'res_id': self.shipping_finance_file_id.id,
            'target': 'current',
        }
    
    @api.depends('finance_lines.amount')  
    def calculate_account_blc(self):
        for record in self:
            total = 0.00
            for line in record.finance_lines:
                try:
                    total += float(line.amount) if line.amount else 0.00
                except ValueError:
                    # Log or skip non-numeric values
                    continue
            record.account_total = total


class AccountMove(models.Model):
    _inherit = "account.move"

    file_ref = fields.Char(string="Move Ref", readonly=True, tracking=True)



class FinanceChargesLine(models.Model):
    """
    Model to manage the Import Charges.
    """
    _name = 'finance.charges.line'
    _description = 'Import Charges'
    _inherit = ['mail.thread', 'mail.activity.mixin'] 
    
    
    product_item = fields.Many2one("product.product", string="Chargeable Service", tracking=True)
    name_id = fields.Char(related='assoc_finance_line.name', store=True, string='Name')
    account_id = fields.Many2one("account.account", string="Account", required=True)
    file_items = fields.Many2one("register.file")
    assoc_finance_line = fields.Many2one("finance.charges", tracking=True)
    amount = fields.Char(string="Amount", readonly=False)

    @api.onchange('product_item')
    def _onchange_product_item(self):
        for record in self:
            record.amount = str(record.product_item.list_price) if record.product_item else ""
            
    
    


