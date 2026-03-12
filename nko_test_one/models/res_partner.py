from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    x_nko_test_one = fields.Boolean(
        string='NKO Test 1',
        default=False,
    )


    x_test_two = fields.Char(
        string='Test 2',
        size=255,
    )
    x_text_2 = fields.Selection(
        selection=[
            ('i', 'I'),
            ('did', 'Did'),
            ('it', 'It'),
        ],
        string='Test 2',
    )
