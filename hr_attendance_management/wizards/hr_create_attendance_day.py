# Copyright (C) 2018 Compassion CH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import timedelta

from odoo import models, fields


class CreateHrAttendance(models.TransientModel):
    _name = 'create.hr.attendance.day'

    date_from = fields.Date(string="Date from")
    date_to = fields.Date(string="Date to")
    employee_ids = fields.Many2many('hr.employee', string='Employee')

    def create_attendance_day(self):
        date_to = fields.Date.from_string(self.date_to)
        att_day = self.env['hr.attendance.day']

        for employee_id in self.employee_ids:
            current_date = fields.Date.from_string(self.date_from)
            while current_date <= date_to:
                already_exist = att_day.search([
                    ('employee_id', '=', employee_id.id),
                    ('date', '=', current_date)
                ])
                if not already_exist:
                    att_day.create({
                        'employee_id': employee_id.id,
                        'date': current_date,
                    })
                current_date = current_date + timedelta(days=1)
