# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, date

today = date.today()

class ShippingDetails(models.Model):
    """
    Model to manage the custom Shipping Details.
    """
    _name = 'shipping.file'
    _description = 'Shipping Details'
    _inherit = ['mail.thread', 'mail.activity.mixin'] 
    
    
    @api.model
    def create(self, vals):
        if vals.get("name", _("New")) == _("New"):
            vals["name"] = self.env["ir.sequence"].next_by_code("shipping.file") or _("New")
        res = super(ShippingDetails, self).create(vals)
        return res
    
    
    register_file_id = fields.Many2one('register.file', string="Register File", ondelete='cascade', readonly=True)
    finance_charges_id = fields.Many2one('finance.charges', string="Finance Charges", ondelete='cascade', readonly=True)
    register_state = fields.Selection(
    related='register_file_id.state',
    string='Register State',
    readonly=True,
    store=True
    )
    name = fields.Char(string='Tracking Number', required=True, copy=False, readonly=True,
                       index=True, default=lambda self: _('New')) 
    partner_id = fields.Many2one('res.partner', string='Customer/Recipient') 
    # tracking_url = fields.Char(string='Tracking URL')
    # carrier_id = fields.Many2one('delivery.carrier', string='Carrier')
    eta_datetime = fields.Datetime(string='Estimated Time of Arrival (ETA)', tracking=True)
    actual_arrival_datetime = fields.Datetime(string='Actual Arrival Time') 


    # --- Charges (from "Charges Req Upon ETA") ---
    # Using Monetary field requires currency_id. Often derived from company or partner.
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', depends=['company_id'], store=True, string='Currency')
    shipping_charges = fields.Monetary(string='Shipping Charges', currency_field='currency_id', tracking=True)
    # charges_requested = fields.Boolean(string='Charges Requested', default=False, tracking=True,
    #                                    help="Indicates if the charges have been formally requested, possibly after ETA confirmation.")

    # --- Documents & DO Release (from "Set Documents for DO Release") ---
    # If specific, mandatory documents are needed, you could use Binary fields:
    # bill_of_lading = fields.Binary(string="Bill of Lading")
    do_released = fields.Boolean(string='Delivery Order Released', default=False, tracking=True,
                                 help="Indicates if the Delivery Order has been released.")
    do_attachment_id = fields.Binary(string="Delivery Order Document", required=False)
    do_release_date = fields.Date(string='DO Release Date')
    
    
    port_attachment_id = fields.Binary(string="Release of Customs Entry", required=False)

    # --- Payment / Finance (from "Payment / Finance") ---
    # payment_state = fields.Selection([
    #     ('not_paid', 'Not Paid'),
    #     ('invoiced', 'Invoiced'),
    #     ('paid', 'Paid'),
    # ], string='Payment Status', default='not_paid', tracking=True)
    # Alternatively, link directly to an invoice:
        
    
    def action_create_finance_charge(self):
        for record in self:
            if not record.register_file_id:
                raise UserError(_("Register File must be set to create a Finance Charge."))
            
            finance_charge = self.env['finance.charges'].create({
                'register_finance_file_id': record.register_file_id.id,
                'shipping_finance_file_id': record.id,
            })
            
            record.finance_charges_id = finance_charge.id
            record.register_file_id.state = 'pending_finance'
                        
            return {
                'type': 'ir.actions.act_window',
                'name': _('Finance Charge'),
                'res_model': 'finance.charges',
                'view_mode': 'form',
                'res_id': finance_charge.id,
                'target': 'current',
            }


    def action_open_register_file(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'register.file',
            'view_mode': 'form',
            'res_id': self.register_file_id.id,
            'target': 'current',
        }
        
    
    def action_open_finance_charges(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'finance.charges',
            'view_mode': 'form',
            'res_id': self.finance_charges_id.id,
            'target': 'current',
        }
        
           
    # @api.depends('carrier_id', 'tracking_number')
    # def _compute_tracking_url(self):
    #     for record in self:
    #         # Logic to build tracking URL based on carrier
    #         record.tracking_url = False # Placeholder

    # def action_confirm(self):
    #     self.write({'state': 'confirmed'})

    # def action_set_in_transit(self):
    #      # Maybe require tracking number first
    #      self.write({'state': 'in_transit'})

    # def action_confirm_eta(self):
    #     # Maybe require ETA datetime
    #     self.write({'state': 'eta_confirmed'})
    #     # Potentially trigger request for charges here
    #     self.write({'charges_requested': True})

    # def action_ready_for_do(self):
    #     # Could check if necessary documents are attached via chatter
    #     self.write({'state': 'ready_for_do'})

    # def action_release_do(self):
    #     self.write({'state': 'do_released', 'do_released': True, 'do_release_date': fields.Date.today()})

    