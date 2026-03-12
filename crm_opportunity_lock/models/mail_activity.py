from odoo import models, _
from odoo.exceptions import UserError


class MailActivity(models.Model):
    _inherit = 'mail.activity'

    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('res_model') == 'crm.lead' and vals.get('res_id'):
                lead = self.env['crm.lead'].browse(vals['res_id'])
                if lead.is_locked:
                    raise UserError(_(
                        'Cannot schedule an activity on a locked opportunity. Unlock it first.'
                    ))
        return super().create(vals_list)
