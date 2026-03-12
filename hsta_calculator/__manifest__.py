{
    'name': 'HSTA Financing Calculator',
    'version': '19.0.1.0.0',
    'summary': 'Odoo Financing Calculator',
    'author': 'HSTA',
    'category': 'Tools',
    'depends': ['web'],
    'data': [
        'views/calculator_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'hsta_calculator/static/src/calculator.js',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
