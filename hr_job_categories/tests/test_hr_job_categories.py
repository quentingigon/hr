# -*- coding:utf-8 -*-
##############################################################################
#
#    Copyright (C) 2014 Savoir-faire Linux. All Rights Reserved.
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp.tests import common


class test_hr_job_categories(common.TransactionCase):
    def setUp(self):
        super(test_hr_job_categories, self).setUp()
        self.employee_model = self.env['hr.employee']
        self.employee_categ_model = self.env['hr.employee.category']
        self.user_model = self.env['res.users']
        self.job_model = self.env['hr.job']
        self.contract_model = self.env['hr.contract']

        # Create a employee
        self.employee_id = self.employee_model.create({'name': 'Employee 1'})

        # Create two employee categories
        self.categ_id = self.employee_categ_model.create(
            {'name': 'Category 1'})
        self.categ_2_id = self.employee_categ_model.create(
            {'name': 'Category 2'})

        # Create two jobs
        self.job_id = self.job_model.create(
            {'name': 'Job 1',
             'category_ids': [(6, 0, [self.categ_id.id])]})

        self.job_2_id = self.job_model.create(
            {'name': 'Job 2',
             'category_ids': [(6, 0, [self.categ_2_id.id])]})

        # Create one contract
        self.contract_id = self.contract_model.create(
            {'name': 'Contract 1',
             'employee_id': self.employee_id.id,
             'wage': 50000})

    def test_write_computes_with_normal_args(self):
        """
        Test that write method on hr_contract computes without error
        when the required data is given in parameter

        data.get('job_id') == True
        vals.get('job_id') == True
        """
        # Check if job categories are written to the employee
        self.contract_id.write({'job_id': self.job_id.id})
        job_categ = [categ.id for categ in self.job_id.category_ids]
        empl_categ = [categ.id for categ in self.employee_id.category_ids]

        self.assertTrue(all(x in empl_categ for x in job_categ))

        # Check if job2 categories are written to the employee
        self.contract_id.write({'job_id': self.job_2_id.id})
        job_categ = [categ.id for categ in self.job_2_id.category_ids]
        empl_categ = [categ.id for categ in self.employee_id.category_ids]

        self.assertTrue(all(x in empl_categ for x in job_categ))
