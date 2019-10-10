# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2019 Compassion CH (http://www.compassion.ch)
#    Releasing children from poverty in Jesus' name
#    @author: Quentin Gigon <gigon.quentin@gmail.com>
#
#    The licence is in the file __manifest__.py
#
##############################################################################

from openupgradelib import openupgrade
from datetime import date


# TODO this migration should work but if made in year 2020, it will not create a period for the year 2019
@openupgrade.migrate(use_env=True)
def migrate(env, version):
    if not version:
        return
    cr = env.cr

    start_date = str(date.today().replace(year=2018, month=1, day=1))
    # Chose this day because its one of the date of execution of the CRON
    end_date = str(date.today().replace(year=2018, month=12, day=31))
    cr.execute("SELECT id FROM hr_employee")
    employee_ids = cr.dictfetchall()

    for employee in employee_ids:

        employee_model = env['hr.employee'].search([
            ('id', '=', employee["id"])
        ], limit=1)

        if employee_model:
            # Calculate extra and lost hours for 2018
            new_balance, lost = employee_model.past_balance_computation(start_date, end_date, 0)

            # Get old balance value
            cr.execute(
                """
                    SELECT
                        balance
                    FROM 
                        hr_employee
                    WHERE
                        id = %s
                """, [employee["id"]])

            old_balance = cr.dictfetchone()["balance"]

            # Initial balance is the diff between old one and new one
            initial_balance = old_balance - new_balance

            # Set initial balance of employee (represent balance before 01.01.2018)
            cr.execute("UPDATE hr_employee SET initial_balance = %s "
                       "WHERE id = %s",
                       (initial_balance, employee['id']))

            # Create a period for the year 2018
            employee_model.create_period(employee["id"],
                                         start_date,
                                         end_date,
                                         new_balance,
                                         initial_balance,
                                         lost,
                                         employee_model.extra_hours_continuous_cap)
            # Update balance value of employee (should be based on the just created period)
            employee_model.compute_balance()
