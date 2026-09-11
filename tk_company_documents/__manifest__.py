# -*- coding: utf-8 -*-
{
    'name': 'Company Document Expiry Notification',
    'description': """
            Company Document and Expiry Notification
    """,
    'summary': 'Company Document and Expiry Notification',
    'version': '18.0.1.0.0',
    'category': 'Customer',
    'author': 'TechKhedut Inc.',
    'company': 'TechKhedut Inc.',
    'maintainer': 'TechKhedut Inc.',
    'website': "https://www.techkhedut.com",
    'depends': [
        'mail',
        'base_setup',
    ],
    'data': [
        # Security
        'security/security_access.xml',
        'security/ir.model.access.csv',
        # data
        'data/company_document_expiry_mail.xml',
        'data/ir_cron.xml',
        'data/sequence.xml',
        # Views
        'views/res_company_views.xml',
        'views/company_document_view.xml',
        'views/document_type_view.xml',
        'views/res_config_settings_view.xml',
        'views/menus.xml',
    ],
    'images': ['static/description/cover.jpg'],
    'license': 'OPL-1',
    'installable': True,
    'application': True,
    'auto_install': False,
}
