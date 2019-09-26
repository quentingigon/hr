# -*- coding: utf-8 -*-

# Copyright (C) 2018 Compassion CH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import datetime
import logging

from odoo import models, fields, api
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    ##########################################################################
    #                                 FIELDS                                 #
    ##########################################################################
    extra_hours_continuous_cap = fields.Boolean(
        help="Set this field to true if you want to have the employee "
             "extra hours to be continuously capped to max_extra_hours and not"
             " only at the cron execution time.")
    annual_balance_date = fields.Date(
        compute='_compute_annual_balance_date')
    current_period_start_date = fields.Date(
        compute="_compute_current_period_start_date", store=False)

    attendance_days_ids = fields.One2many('hr.attendance.day', 'employee_id',
                                          "Attendance days")
    balance = fields.Float(string='Balance', compute='compute_balance', store=True)
    initial_balance = fields.Float(string='Initial Balance before 2018',
                                   compute='_compute_initial_balance',
                                   store=True)

    extra_hours_lost = fields.Float(compute='compute_balance', store=True)

    last_update_date = fields.Date(string='Date of last balance computation')
    last_update_balance = fields.Float(string='Last value calculated for the balance after 2018')

    previous_period_continuous_cap = fields.Boolean(readonly=True)
    previous_period_balance = fields.Float(oldname="annual_balance")
    previous_period_lost_hours = fields.Float(readonly=True)

    penultimate_period_balance = fields.Float()
    penultimate_period_lost_hours = fields.Float()

    balance_formatted = fields.Char(string="Balance",
                                    compute='_compute_formatted_hours')

    time_warning_balance = fields.Char(compute='_compute_time_warning_balance')

    time_warning_today = fields.Char(compute='_compute_time_warning_today')

    extra_hours_today = fields.Char(compute='_compute_extra_hours_today')

    today_hour = fields.Char(compute='_compute_today_hour')

    today_hour_formatted = fields.Char(compute='_compute_today_hour_formatted')

    work_location_id = fields.Many2one('hr.attendance.location',
                                       string='Work Location')

    work_location = fields.Char(compute='_compute_work_location')

    ##########################################################################
    #                             FIELDS METHODS                             #
    ##########################################################################

    @api.multi
    def _compute_initial_balance(self):
        # TODO get value for initial_balance in DB (this value should be entered manually for each employee and
        #  represent their balance at the beginning of 2018)
        for employee in self:
            employee.initial_balance = 0

    @api.multi
    def _compute_annual_balance_date(self):
        for employee in self:
            employee.annual_balance_date = \
                self.env['base.config.settings'].create({})\
                    .get_next_balance_cron_execution()

    @api.multi
    def _compute_current_period_start_date(self):
        for employee in self:
            employee.current_period_start_date = \
                self.env['base.config.settings'].create({}) \
                    .get_last_balance_cron_execution()

    @api.multi
    def _compute_work_location(self):
        for employee in self:
            actual_location = self.env['hr.attendance'].search([
                ('employee_id', '=', employee.id),
                ('check_out', '=', False)], limit=1)

            employee.work_location = actual_location.location_id.name

    @api.multi
    @api.depends('extra_hours_continuous_cap')
    def update_period_cap(self):
        for employee in self:
            employee.compute_balance(store=True)

    @api.multi
    def compute_balance(self, store=False):
        for employee in self:
            employee_history = self.env['hr.employee.balance.history'].search([
                ('employee_id', '=', employee.id)
            ])
            start_date = None
            end_date = fields.Date.to_string(datetime.date.today())
            balance = None
            # If there is an history for this employee, take values of last row
            if employee_history:
                employee_history_sorted = sorted(employee_history, key=lambda r: r.date)
                start_date = employee_history_sorted[-1].date
                balance = employee_history_sorted[-1].balance
            # Compute from 01.01.2018
            else:
                start_date = datetime.date.today().replace(year=2018, month=1, day=1)
                balance = employee.initial_balance

            extra, lost = employee.past_balance_computation(
                start_date=start_date,
                end_date=end_date,
                existing_balance=balance)

            employee.balance = extra
            employee.extra_hours_lost = lost

            if store:
                previous_balance = None
                if employee_history:
                    previous_balance = employee_history[-1].balance
                else:
                    previous_balance = employee.initial_balance
                self.env['hr.employee.balance.history'].create({
                    'employee_id': employee.id,
                    'date': end_date,
                    'balance': extra,
                    'previous_balance': previous_balance,
                    'lost': lost,   # TODO lost is always == 0 at second CRON execution
                    'continuous_cap': employee.extra_hours_continuous_cap
                })

    # Called when past periods must be updated (balance), often after an update to an attendance_day
    def update_past_periods(self, start_date, end_date, balance):
        for employee in self:
            extra, lost = employee.past_balance_computation(
                start_date=start_date,
                end_date=end_date,
                existing_balance=balance)

            # Recompute period concerned by attendance_day modification
            current_period = self.env['hr.employee.balance.history'].search([
                ('employee_id', '=', employee.id),
                ('date', '=', end_date)
            ], limit=1)
            current_period.write({
                'balance': extra,
                'lost': current_period.lost,
                'previous_balance': balance
            })

            employee_history = self.env['hr.employee.balance.history'].search([
                ('employee_id', '=', employee.id),
                ('date', '>', end_date)
            ], order='date asc')

            previous_balance = extra

            for entry in employee_history:
                diff = entry.balance - entry.previous_balance
                entry.write({
                    'previous_balance': previous_balance,
                    'balance': previous_balance + diff,
                })
                previous_balance = previous_balance + diff

    @api.multi
    def is_continuous_cap_at_date(self, date):
        """
        This method return the status of the employee at the specified date.
        A True value means that the employee was capped to max_extra_hours at
        the specified date.
        Can Raise a ValueError if we don't have information about the period in
        which date is.
        :param date: The date of the desired status
        :return: Boolean whether it was a continuous or annual capping.
        """

        for employee in self:
            upper_bound_history = self.env['hr.employee.balance.history'].search([
                ('employee_id', '=', employee.id),
                ('date', '>=', date)
            ], order='date asc', limit=1)

            if upper_bound_history:
                return upper_bound_history.continuous_cap
            else:
                return True   # default value TODO fix
                # undefined as we don't know the period and the status
                # raise ValueError("Date is outside history")

    @api.multi
    def complete_balance_computation(self, start_date=None, end_date=None,
                                     existing_balance=0):
        """
        Compute the running balances extra and lost hours of the employee
        between start and end date. We go through the days and add the paid
        hours, keeping an array of the value at each day.
        :param start_date: Start date of the period of interest
        :param end_date: End date of the period of interest
        :param existing_balance: The extra hours balance of the employee at
                                 start_date
        :return: 3 lists:
                 (a) list of each date for which we have data, sorted
                 (b) the corresponding cumulative sum of extra hours for each
                     day present in (a)
                 (c) the cumulative sum of lost hours for each day in (a).
                     (increasing values as no lost hours can be deduced).
        """
        self.ensure_one()
        max_extra_hours = self.env['base.config.settings'].create({})\
            .get_max_extra_hours()
        if not start_date:
            start_date = fields.Date.to_string(
                datetime.date.today().replace(month=1, day=1))
        if not end_date:
            end_date = fields.Date.to_string(datetime.date.today())

        if not isinstance(start_date, basestring):
            start_date = fields.Date.to_string(start_date)
        if not isinstance(end_date, basestring):
            end_date = fields.Date.to_string(end_date)

        if start_date > end_date:
            raise ValidationError("Start date must be earlier than end date.")

        attendance_day_ids = self.attendance_days_ids.filtered(
            lambda r: start_date <= r.date < end_date)

        days = [start_date]
        extra_hours_sum = [existing_balance]
        lost_hours = [0]
        attendance_days_sorted = sorted(attendance_day_ids,
                                        key=lambda r: r.date)
        for day in attendance_days_sorted:
            days.append(day.date)
            extra_hours_sum.append(extra_hours_sum[-1] + day.day_balance)
            lost_hours.append(lost_hours[-1])
            if extra_hours_sum[-1] > max_extra_hours and \
                    self.is_continuous_cap_at_date(day.date):
                lost_hours[-1] += extra_hours_sum[-1] - max_extra_hours
                extra_hours_sum[-1] = max_extra_hours

        return days, extra_hours_sum, lost_hours

    @api.multi
    def past_balance_computation(self, start_date=None, end_date=None,
                                 existing_balance=0):
        """
        Compute the balance of extra and lost horus at end_date.
        :param start_date: Start date of the computation
        :param end_date: Date of desired data
        :param existing_balance: Existing extra hours balance at start_date
        :return: Tuple of integers (extra_hours, lost_hours)
        """
        _, extra_hours_sum, lost_hours = self.complete_balance_computation(
            start_date=start_date,
            end_date=end_date,
            existing_balance=existing_balance)
        if len(extra_hours_sum) < 1:
            _logger.warning("Balance computation on period without data")
            return 0, 0
        return extra_hours_sum[-1], lost_hours[-1]

    @api.model
    def _cron_create_attendance(self, domain=None, day=None):
        att_day = self.env['hr.attendance.day']
        employees = self.search(domain or [])
        if day is None:
            day = fields.Date.today()
        for employee in employees:
            # check if an entry already exists. If yes, it will not be
            # recreated
            att_days = att_day.search(
                [('date', '=', day), ('employee_id', '=', employee.id)])
            if att_days:
                continue

            # check that the employee is currently employed.
            contracts_valid_today = self.env['hr.contract'].search([
                ('employee_id', '=', employee.id),
                ('date_start', '<=', day),
                '|', ('date_end', '=', False), ('date_end', '>=', day)
            ])

            if not att_days and contracts_valid_today:
                att_day.create({
                    'date': day,
                    'employee_id': employee.id
                })

    @api.model
    def _cron_compute_annual_balance(self):
        """
        Roll over the balance of extra hours for the period ranging from the
        last call to this cron to today. The balance of the previous period
        will be stored for recomputation in case of change.
        :return: Nothing
        """
        employees = self.search([])
        for employee in employees:
            employee.compute_balance(store=True)

    @api.multi
    def _update_past_period_balance(self):
        """
        This function is meant to be run some time after
        _cron_compute_annual_balance(). It will update the values of the
        previous period as these can have been changed.
        :return: Nothing
        """
        config = self.env['base.config.settings'].create({})

        last_computation = \
            config.get_last_balance_cron_execution()
        penultimate_computation = \
            config.get_penultimate_balance_cron_execution()

        for employee in self:
            extra, lost = employee.past_balance_computation(
                start_date=penultimate_computation,
                end_date=last_computation,
                existing_balance=employee.penultimate_period_balance)

            new_balance = extra
            new_lost = employee.penultimate_period_lost_hours + lost
            if not employee.previous_period_continuous_cap:
                # not continuous extra hours -> cap at cron execution
                new_balance = min(config.get_max_extra_hours(), new_balance)
                new_lost += extra - new_balance
            employee.previous_period_balance = new_balance
            employee.previous_period_lost_hours = new_lost

    @api.multi
    @api.depends('today_hour')
    def _compute_extra_hours_today(self):
        for employee in self:
            employee.extra_hours_today = \
                employee.convert_hour_to_time(employee.today_hour)

    @api.multi
    def _compute_time_warning_balance(self):
        max_extra_hours = self.env['base.config.settings'].create({}) \
            .get_max_extra_hours()
        for employee in self:
            if employee.balance < 0:
                employee.time_warning_balance = 'red'
            elif max_extra_hours and \
                    employee.balance >= max_extra_hours * 2 / 3:
                employee.time_warning_balance = 'orange'
            else:
                employee.time_warning_balance = 'green'

    @api.multi
    @api.depends('today_hour')
    def _compute_time_warning_today(self):
        for employee in self:
            employee.time_warning_today = \
                'red' if float(employee.today_hour) < 0 else 'green'

    @api.multi
    def _compute_today_hour(self):
        for employee in self:
            current_att_day = self.env['hr.attendance.day'].search([
                ('employee_id', '=', employee.id),
                ('date', '=', fields.Date.today())])
            employee.today_hour = \
                employee.calc_today_hour() - current_att_day.due_hours

    @api.multi
    def _compute_formatted_hours(self):
        for employee in self:
            employee.balance_formatted = \
                employee.convert_hour_to_time(employee.balance)

    @api.multi
    @api.depends('today_hour')
    def _compute_today_hour_formatted(self):
        for employee in self:
            today_hour = employee.calc_today_hour()
            employee.today_hour_formatted = \
                employee.convert_hour_to_time(today_hour)

    @api.model
    def convert_hour_to_time(self, hour):
        formatted = '{:02d}:{:02d}'.format(*divmod(int(abs(
            float(hour) * 60)), 60))
        return '-' + formatted if hour < 0 else formatted

    # TODO base it on att_day.total_attendance
    @api.multi
    def calc_today_hour(self):
        self.ensure_one()

        today = fields.Date.today()
        attendances_today = self.env['hr.attendance'].search([
            ('employee_id', '=', self.id), ('check_in', '>=', today)])
        worked_hours = 0

        for attendance in attendances_today:
            if attendance.check_out:
                worked_hours += attendance.worked_hours
            else:
                delta = datetime.datetime.now() \
                        - fields.Datetime.from_string(attendance.check_in)
                worked_hours += delta.total_seconds() / 3600.0

        return worked_hours

    def open_balance_graph(self):
        """
        Populates data for history graph and open the view
        :return: action opening the view
        """
        self.ensure_one()
        self.env['balance.evolution.graph'].populate_graph(self.id)
        return {
            'name': 'Extra hours evolution',
            'type': 'ir.actions.act_window',
            'res_model': 'balance.evolution.graph',
            'context': {"graph_mode": "bar"},
            'view_type': 'form',
            'view_mode': 'graph',
            'domain': [('employee_id', '=', self.id)],
            'target': 'current',
        }

    def get_total_balance(self):
        self.ensure_one()
        self._compute_initial_balance()
        self.compute_balance()
