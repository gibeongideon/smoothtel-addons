from odoo import models, fields, api


class SoApproval(models.Model):
    _inherit = "sale.order"

    button_visibility = fields.Boolean(string="Approve button")

    state = fields.Selection(
        selection_add=[('waiting', 'Waiting for Approval')],
        string='Status',
        readonly=True
    )

    @api.model
    def _setup_complete(self):
        super()._setup_complete()
        # Reorder state field after all modules are loaded
        state_field = self._fields.get('state')
        if state_field:
            ordered = [
                ('draft', 'Quotation'),
                ('waiting', 'Waiting for Approval'),
                ('sent', 'Quotation Sent'),
                ('sale', 'Sales Order'),
                ('done', 'Locked'),
                ('cancel', 'Cancelled'),
            ]
            state_field.selection = ordered




    @api.onchange("order_line")
    def approval(self):
        # ❌ Problem: This loop iterates over order_line records, not the order itself.
        # ❌ Problem: self.write() should NEVER be used in an onchange method — it commits data during UI preview.
        # 🧱 Commented out and replaced with a safer logic explanation below.
        #
        # for record in self.order_line:
        #     if record.price_unit < record.product_template_id.list_price or \
        #             record.price_unit > record.product_template_id.list_price:
        #         self.write({'button_visibility': True})
        #         # return {
        #         #     'warning': {
        #         #         'title': 'Warning',
        #         #         'message': 'You need Approval from manager'
        #         #     }
        #         # }

        # ✅ Correct approach (suggested): just update the field value in memory
        for order in self:
            show_button = any(
                line.price_unit != line.product_template_id.list_price
                for line in order.order_line
            )
            order.button_visibility = show_button


    

    def button_manager(self):
        # ✅ Fine — moves quotation to waiting state
        self.write({'state': 'waiting'})

    def button_approve(self):
        self.write({'state': 'sent'})
        return self.action_quotation_send()
        # return self.action_confirm()


    # def button_approve(self):
        # ⚠️ Potential issue: setting state to 'sent' may confuse the normal workflow.
        #    'sent' means quotation has been sent to customer, not manager-approved.
        # 🧱 If this is meant to approve, comment this and use 'sale' or call action_confirm().
        #
        # self.write({'state': 'sent'})
        # return self.action_quotation_send()

        # ✅ Suggested safe version:
        # for order in self:
        #     order.write({'state': 'sale', 'button_visibility': False})
        #     order.action_confirm()
        # return True

# def button_approve(self):
        # for order in self:
        #     if order.state in ['draft', 'sent', 'waiting']:
        #         order.action_confirm()
        #     order.button_visibility = False
        # return True


    def button_reject(self):
        # ✅ Fine — sends it back to draft.
        self.write({'state': 'draft'})





# from odoo import models, fields, api


# class SoApproval(models.Model):
#     _inherit = "sale.order"

#     button_visibility = fields.Boolean(string="Approve button")
#     state = fields.Selection(selection_add=[('waiting', 'Waiting for Approval')
#                                             ], string='Status', readonly=True
#                              )

#     @api.onchange("order_line")
#     def approval(self):
#         for record in self.order_line:
#             if record.price_unit < record.product_template_id.list_price or \
#                     record.price_unit > record.product_template_id.list_price:
#                 self.write({'button_visibility': True})
#                 # return {
#                 #     'warning': {
#                 #         'title': 'Warning',
#                 #         'message': 'You need Approval from manager'
#                 #     }
#                 # }

#     def button_manager(self):
#         self.write({'state': 'waiting'})

#     def button_approve(self):
#         self.write({'state': 'sent'})
#         return self.action_quotation_send()

#     def button_reject(self):
#         self.write({'state': 'draft'})
