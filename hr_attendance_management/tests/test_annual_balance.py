# Copyright (C) 2018 Compassion CH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from datetime import datetime, timedelta
from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import SavepointCase
import logging

logger = logging.getLogger(__name__)


class TestAnnualBalance(SavepointCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.jack = cls.env.ref('hr.employee_fme')
        cls.gilles = cls.env.ref('hr.employee_qdp')
        cls.pieter = cls.env.ref('hr.employee_root')
        cls.michael = cls.env.ref('hr.employee_niv')

        # Add work schedule (8h/work days) for Gilles, Jack and Michael
        cls.gilles.calendar_id = cls.env.ref('resource.timesheet_group1')
        cls.jack.calendar_id = cls.env.ref('resource.timesheet_group1')
        cls.michael.calendar_id = cls.env.ref('resource.timesheet_group1')

        cls.config = cls.env['res.config.settings'].create({})

        # Create attendance days for employees
        attendances = cls.env['hr.attendance'].search([], order='check_in')
        cls.all_attendances = attendances

        cls.monday = (datetime.now().date()
                      - timedelta(days=datetime.now().weekday() + 7))
        cls.tuesday = cls.monday + timedelta(days=1)
        cls.wednesday = cls.monday + timedelta(days=2)
        cls.thursday = cls.monday + timedelta(days=3)
        cls.friday = cls.monday + timedelta(days=4)
        cls.saturday = cls.monday + timedelta(days=5)
    ##########################################################################
    #                           ATTENDANCE DAY                               #
    ##########################################################################

    def create_first_attendance(self, date, employee):
        """
        Create an attendance for last friday from 09:00 to 17:30 for a
        duration of 8 hours and 30 minutes. A break of 30 minutes is created by
        the system, thereby the paid hours should be 8 hours and the rule
        break 7-9.
        :return: None
        """

        start = date.strftime('%Y-%m-%d 08:30')
        stop = date.strftime('%Y-%m-%d 17:30')
        self.env['hr.attendance'].create({
            'check_in': start,
            'check_out': stop,
            'employee_id': employee.id,
        })

    def test_annual_no_limit(self):
        self.config.max_extra_hours = 2
        self.config.set_max_extra_hours()
        self.assertEqual(self.config.get_max_extra_hours(), 2)
        self.config.free_break = 0.25
        self.config.set_free_break()
        self.assertEqual(self.config.get_free_break(), 0.25)

        self.michael.extra_hours_continuous_cap = False
        self.jack.extra_hours_continuous_cap = True
        for person in [self.jack, self.michael]:
            self.create_first_attendance(self.monday, person)
            self.create_first_attendance(self.tuesday, person)
            self.create_first_attendance(self.wednesday, person)
            self.create_first_attendance(self.thursday, person)
            self.create_first_attendance(self.friday, person)
            person.compute_balance()

        # Both jack and michael have worked 5 days with 0.5 hours extra hours
        # each day.
        self.assertEqual(self.jack.balance, 2)
        self.assertEqual(self.jack.extra_hours_lost, 0.5)
        self.assertEqual(self.michael.balance, 2.5)
        self.assertEqual(self.michael.extra_hours_lost, 0)
        # Upon switching to continuous computation, michael should loose up to
        # limit of extra hours.
        self.michael.extra_hours_continuous_cap = True
        self.michael.compute_balance()
        self.assertEqual(self.michael.balance, 2)
        self.assertEqual(self.michael.extra_hours_lost, 0.5)
        # Switching back should come back to 2.5 extra hours.
        self.michael.extra_hours_continuous_cap = False
        self.michael.compute_balance()
        self.assertEqual(self.michael.balance, 2.5)
        self.assertEqual(self.michael.extra_hours_lost, 0)

        # Execute cron
        self.env['hr.employee.period'].search([
            ('employee_id', '=', self.jack.id)
        ]).unlink()
        self.env['hr.employee.period'].search([
            ('employee_id', '=', self.michael.id)
        ]).unlink()
        self.jack._cron_compute_annual_balance()
        # michael extra hours should be affected by the yearly cutoff
        self.assertEqual(self.jack.balance, 2)
        self.assertEqual(self.michael.balance, 2.5)

        # Now will modify an attendance in the recent past and see if the
        # update catch it correctly.
        for person in [self.michael, self.jack]:
            person.attendance_days_ids[-1].attendance_ids[-1].check_out = \
                fields.Datetime.from_string(
                    person.attendance_days_ids[-1].attendance_ids[-1].check_out) + timedelta(hours=3)
        self.michael._cron_compute_annual_balance()
        self.assertEqual(self.jack.balance, 2)
        self.assertEqual(self.michael.balance, 5.25)



