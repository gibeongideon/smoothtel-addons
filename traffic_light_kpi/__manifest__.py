{
    'name': 'KPI Traffic Light System',
    'version': '18.0.1.0.0',
    'summary': 'Real-time role-based KPI tracking with traffic light indicator',
    'description': """
        Monitors employee performance based on predefined KPIs assigned to
        job positions. Displays a real-time Red/Yellow/Green traffic light
        in the systray for each logged-in user.
    """,
    'author': 'Custom Development',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'hr',
        'hr_skills',
        'crm',
        'sale_management',
        'purchase',
        'mail',
        'web',
        'helpdesk',
        'approvals',
        'hr_expense',
    ],
    'data': [
        'security/kpi_security.xml',
        'security/ir.model.access.csv',
        'data/kpi_cron.xml',
        'views/kpi_definition_views.xml',
        'views/kpi_result_views.xml',
        'views/res_config_settings_views.xml',
        'views/res_users_views.xml',
        'views/menu.xml',
    ],
    'demo': [
        'data/kpi_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'traffic_light_kpi/static/src/css/kpi_traffic_light.css',
            'traffic_light_kpi/static/src/xml/kpi_traffic_light_systray.xml',
            'traffic_light_kpi/static/src/js/kpi_traffic_light_systray.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
