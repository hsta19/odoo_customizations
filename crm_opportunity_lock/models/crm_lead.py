from odoo import models, fields, _
from odoo.exceptions import UserError

LOCK_FIELDS = frozenset({'is_locked', 'locked_by', 'locked_date'})


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    is_locked = fields.Boolean(
        string='Locked',
        default=False,
        copy=False,
        tracking=True,
    )
    locked_by = fields.Many2one(
        'res.users',
        string='Locked By',
        readonly=True,
        copy=False,
    )
    locked_date = fields.Datetime(
        string='Locked On',
        readonly=True,
        copy=False,
    )

    def action_lock(self):
        for rec in self:
            rec.write({
                'is_locked': True,
                'locked_by': self.env.user.id,
                'locked_date': fields.Datetime.now(),
            })

    def action_unlock(self):
        for rec in self:
            rec.write({
                'is_locked': False,
                'locked_by': False,
                'locked_date': False,
            })

    def write(self, vals):
        if not (set(vals.keys()) <= LOCK_FIELDS):
            locked = self.filtered('is_locked')
            if locked:
                raise UserError(_(
                    'The opportunity "%s" is locked. Unlock it before making changes.',
                    locked[0].name,
                ))
        return super().write(vals)
