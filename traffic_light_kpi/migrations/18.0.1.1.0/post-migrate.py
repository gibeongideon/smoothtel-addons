def migrate(cr, version):
    """Move KPIs still on the old 10:00-16:30 default to working hours 07:30-17:00."""
    cr.execute(
        """
        UPDATE kpi_definition
           SET operating_hour_start = 7.5,
               operating_hour_end = 17.0
         WHERE operating_hour_start = 10.0
           AND operating_hour_end = 16.5
        """
    )
