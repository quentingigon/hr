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

from openerp.osv import fields, orm


class hr_contract(orm.Model):
    _inherit = 'hr.contract'

    @api.one
    @api.depends('contract_job_ids')
    def _get_main_job_position(self):
        """
        Get the main job position from the field contract_job_ids which
        contains one and only one record with field is_main_job == True
        """
        main_job = self.contract_job_ids.filtered('is_main_job') or False
        if main_job:
            main_job = main_job[0].job_id.id
        self.job_id = main_job

    contract_job_ids = fields.One2many('hr.contract.job',
                                       'contract_id',
                                       string='Jobs')

        # Modify the job_id field so that it points to the main job
        'job_id': fields.function(
            _get_main_job_position,
            string="Job Title",
            method=True,
            type="many2one",
            relation="hr.job",
            store={
                'hr.contract': (
                    lambda self, cr, uid, ids, c={}: ids,
                    ['contract_job_ids'],
                    10),
                'hr.contract.job': (
                    lambda self, cr, uid, ids, c={}: [
                        contract_job.contract_id.id for contract_job
                        in self.pool['hr.contract.job'].browse(cr, uid, ids)
                    ],
                    ['contract_id'],
                    10)
            }
        ),
    }

    @api.multi
    @api.constrains('contract_job_ids.is_main_job')
    def _check_one_main_job(self):
        for contract in self:
            # if the contract has no job assigned, a main job
            # is not required. Otherwise, one main job assigned is
            # required.
            if contract.contract_job_ids:
                main_jobs = contract.contract_job_ids.filtered('is_main_job')
                if len(main_jobs) != 1:
                    return False
        return True

    _constraints = [
        (
            _check_one_main_job,
            "You must assign one and only one job position as main "
            "job position.",
            ['parent_id']
        ),
    ]
