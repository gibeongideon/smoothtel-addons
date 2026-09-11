{
    'name': "Logistics",
    'summary': """
        Manages a logistics workflow.""",
    'description': """
        This module implements a specific logistics process including registration,
        shipping, finance, port operations, transport, and depot operations.
        - Bill of Lading Registration
        - State-based workflow management
        - Tracking key stages and information
    """,
    'author': "Muhindo Kiro", 
    'category': 'Tools',
    'version': '18.0',
    'depends': ['base', 'mail', 'contacts', 'accountant', 'sale_management', 'stock'], 
    'data': [
        'security/ir.model.access.csv',
        'views/register_views.xml',
        'views/finance_charges_views.xml',
        'views/shipping_views.xml',
        'data/sequence.xml',
        'views/menu_actions.xml',
        'views/menu_items.xml',
    ],
    
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'AGPL-3',
    
}
