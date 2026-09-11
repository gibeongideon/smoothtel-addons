# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, date

today = date.today()

class RegisterFile(models.Model):
    """
    Model to manage the custom Register File.
    """
    _name = 'register.file'
    _description = 'Register File'
    _inherit = ['mail.thread', 'mail.activity.mixin'] 
    
    @api.model
    def create(self, vals):
        if vals.get("name", _("New")) == _("New"):
            vals["name"] = self.env["ir.sequence"].next_by_code("register.file") or _("New")
        res = super(RegisterFile, self).create(vals)
        return res
    
    # --- Fields based on the 'Register' box ---
    shipping_file_id = fields.Many2one('shipping.file', string="Shipping File", readonly=True, store=True)
    # shipping_file_count = fields.Integer(
    #     string="Shipping File", compute='_compute_shipping_file_count')
    chargeable_file_items = fields.One2many("finance.charges.line", "file_items")
    name = fields.Char(string='File Reference', required=True, copy=False, readonly=True,
                       index=True, default=lambda self: _('New')) 
    bl_number = fields.Char(string='BL Number', required=True, tracking=True)
    consignee_name = fields.Many2one("res.partner", string='Consignee Name', tracking=True)
    container_number = fields.Char(string='Container No.', tracking=True)
    commodity_name = fields.Char(string='Commodity Name', tracking=True)
    final_destination = fields.Many2one("res.country", string='Final Destination', tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('awaiting_shipping', 'Shipping'),
        ('pending_finance', 'Finance Clearance'),
        ('invoiced', 'Invoiced'),
        ('ready_do', 'DO Processing'),
        ('pending_port_ops', 'Port Operations'),
        ('loading_in_progress', 'Delivery in Progress'),
        ('return_in_progress', 'Return in Progress'),
        ('container_dropped', 'Container at Depot'),
        ('validation_closure', 'Validation'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled')
    ], string="Status", default='draft', tracking=True)
    
    
    # import_charges_paid = fields.Boolean("Import Charges Paid")
    # kpa_charges_paid = fields.Boolean("KPA Charges Paid")
    # demurrage_paid = fields.Boolean("Demurrage Paid")
    
    
    # def action_awaiting_shipping(self):
    #     self.ensure_one()
    #     self.state = 'awaiting_shipping'

    def action_pending_finance(self):
        self.ensure_one()
        self.state = 'pending_finance'

    def action_ready_do(self):
        self.ensure_one()
        if not (self.import_charges_paid and self.kpa_charges_paid):
            raise UserError("Ensure Import and KPA Charges are paid before proceeding.")
        self.state = 'ready_do'

    def action_pending_port_ops(self):
        self.ensure_one()
        self.state = 'pending_port_ops'

    def action_loading(self):
        self.ensure_one()
        self.state = 'loading_in_progress'

    def action_return_progress(self):
        self.ensure_one()
        self.state = 'return_in_progress'

    def action_container_dropped(self):
        self.ensure_one()
        self.state = 'container_dropped'

    def action_validation(self):
        self.ensure_one()
        if not self.demurrage_paid:
            raise UserError("Demurrage must be cleared before closure.")
        self.state = 'validation_closure'

    def action_done(self):
        self.ensure_one()
        self.state = 'done'

    # def action_cancel(self):
    #     self.ensure_one()
    #     self.state = 'cancelled'
        
    def action_cancel(self):
        if self:
            self.sudo().write({"state": "cancelled"})
        
        
    def action_create_shipping_file(self):
        self.ensure_one()
        shipping = self.env['shipping.file'].create({
            'partner_id': self.consignee_name.id,
            'register_file_id': self.id,
        })
        self.shipping_file_id = shipping.id
        
        self.state = 'awaiting_shipping'

        # Instead of opening shipping file directly, reload current form
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'register.file',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
        }
        
    def action_open_shipping_file(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'shipping.file',
            'view_mode': 'form',
            'res_id': self.shipping_file_id.id,
            'target': 'current',
        }
        
    