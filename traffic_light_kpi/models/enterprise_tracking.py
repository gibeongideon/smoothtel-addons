from odoo import fields, models


class ApprovalRequest(models.Model):
    _inherit = 'approval.request'

    def action_approve(self, approver=None):
        result = super().action_approve(approver=approver)
        timestamp = fields.Datetime.now()
        for request in self:
            current_approvers = approver if isinstance(approver, models.BaseModel) else request.approver_ids.filtered(
                lambda line: line.user_id == self.env.user and line.status == 'approved'
            )
            (request.approver_ids & current_approvers).sudo().write({'decision_date': timestamp})
        return result

    def action_refuse(self, approver=None):
        result = super().action_refuse(approver=approver)
        timestamp = fields.Datetime.now()
        for request in self:
            current_approvers = approver if isinstance(approver, models.BaseModel) else request.approver_ids.filtered(
                lambda line: line.user_id == self.env.user and line.status == 'refused'
            )
            (request.approver_ids & current_approvers).sudo().write({'decision_date': timestamp})
        return result

    def action_withdraw(self, approver=None):
        result = super().action_withdraw(approver=approver)
        if isinstance(approver, models.BaseModel):
            approver.sudo().write({'decision_date': False})
        return result

    def action_draft(self):
        result = super().action_draft()
        self.mapped('approver_ids').sudo().write({'decision_date': False})
        return result

    def action_cancel(self):
        result = super().action_cancel()
        self.mapped('approver_ids').sudo().write({'decision_date': False})
        return result


class ApprovalApprover(models.Model):
    _inherit = 'approval.approver'

    decision_date = fields.Datetime(string='Decision Date', copy=False, readonly=True)


class HrExpenseSheet(models.Model):
    _inherit = 'hr.expense.sheet'

    submitted_on = fields.Datetime(string='Submitted On', copy=False, readonly=True)

    def _do_submit(self):
        result = super()._do_submit()
        self.sudo().write({'submitted_on': fields.Datetime.now()})
        return result

    def _do_reset_approval(self):
        result = super()._do_reset_approval()
        self.sudo().write({'submitted_on': False})
        return result
