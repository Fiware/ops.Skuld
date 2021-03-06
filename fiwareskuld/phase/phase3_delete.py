#!/usr/bin/env python
# -- encoding: utf-8 --
#
# Copyright 2015 Telefónica Investigación y Desarrollo, S.A.U
#
# This file is part of FI-Core project.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
#
# You may obtain a copy of the License at:
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#
# See the License for the specific language governing permissions and
# limitations under the License.
#
# For those usages not covered by the Apache version 2.0 License please
# contact with opensource@tid.es
#
from os import environ as env
import os.path
import cPickle as pickle
import datetime

from fiwareskuld.user_resources import UserResources
from fiwareskuld.utils import log

import conf.settings

__author__ = 'chema'

logger = log.init_logs('phase3')

images_in_use = None
free_trust_id = False
users_list = list()
report = dict()

if os.path.exists('imagesinuse.pickle'):
    images_in_use = pickle.load(open('imagesinuse.pickle'))

# clean credential
if 'OS_USERNAME' in env:
    del env['OS_USERNAME']
if 'OS_TENANT_NAME' in env:
    del env['OS_TENANT_NAME']
if 'OS_TENANT_ID' in env:
    del env['OS_TENANT_ID']
if 'OS_TRUST_ID' in env:
    del env['OS_TRUST_ID']
if 'OS_PASSWORD' in env:
    del env['OS_PASSWORD']

trustee = password = None

if os.path.exists('users_trusted_ids.txt'):
    # The output was generated by the process that create trust-ids
    use_trust_ids = True
    lines = open('users_trusted_ids.txt').readlines()
    if 'DONT_FREE_TRUST_ID' not in env:
            free_trust_id = True

    if 'TRUSTEE_PASSWORD' in env:
        password = env['TRUSTEE_PASSWORD']
    elif 'TRUSTEE_PASSWORD' in dir(conf.settings):
        password = conf.settings.TRUSTEE_PASSWORD
    else:
        msg = 'TRUSTEE_PASSWORD must be defined, either in settings or environ'
        raise Exception(msg)

    if 'TRUSTEE_USER' in env:
        trustee = env['TRUSTEE_USER']
    else:
        trustee = conf.settings.TRUSTEE

elif os.path.exists('users_credentials.txt'):
    # The output was generated by the process that change the passwords
    use_trust_ids = False
    lines = open('users_credentials.txt').readlines()
else:
    raise Exception("user_trusted_ids.txt or users_credentials.txt must exists")


count = 0
total = len(lines)
for line in lines:
    try:
        count += 1
        if use_trust_ids:
            (user, trust_id, user_id) = line.strip().split(',')
            logger.info('Obtaining resources of user {0} ({1}/{2})'.format(
                user, count, total))
            user_resources = UserResources(trustee, password,
                                           trust_id=trust_id)
        else:
            (user, password, tenant_id) = line.strip().split(',')
            logger.info('Obtaining resources of user ' + user)
            user_resources = UserResources(user, password, tenant_id)

        if images_in_use:
            user_resources.imagesinuse = images_in_use

        user_id = user_resources.user_id
        logger.info('user ' + user + ' has id ' + user_id)
        resources_before = user_resources.get_resources_dict()

        # check if user does not have any resources and
        all_free = True
        for key in resources_before:
            if resources_before[key]:
                all_free = False
                break
        if all_free:
            report[user_id] = (resources_before, resources_before, True)
            msg = 'User {0} does not have any resources to free'
            logger.info(msg.format(user_resources.user_id))

            if free_trust_id:
                try:
                    user_resources.free_trust_id()
                except Exception, e:
                    msg = 'Error freeing trust_id of user {0}. Cause: {1}'
                    logger.error(msg.format(user_resources.user_id, str(e)))
        else:
            report[user_id] = resources_before
            users_list.append(user_resources)

    except Exception, e:
        msg = 'Obtaining resources of user {0} failed. Cause: {1}'
        logger.error(msg.format(user, str(e)))

# free resources; group by priorities and delete all the user's resources with
# the some priority before starting with the next priority, to avoid pauses
total_free = dict()
count = 0
total = len(users_list)
for user_resources in users_list:
    user_id = user_resources.user_id
    count += 1
    msg = "Freeing resources priority 1 user: {0} ({1}/{2})"
    logger.info(msg.format(user_id, count, total))
    user_resources.delete_tenant_resources_pri_1()

count = 0
for user_resources in users_list:
    user_id = user_resources.user_id
    count += 1
    msg = "Freeing resources priority 2 user: {0} ({1}/{2})"
    logger.info(msg.format(user_id, count, total))
    user_resources.delete_tenant_resources_pri_2()

count = 0
for user_resources in users_list:
    user_id = user_resources.user_id
    count += 1
    msg = "Freeing resources priority 3 user: {0} ({1}/{2})"
    logger.info(msg.format(user_id, count, total))
    user_resources.delete_tenant_resources_pri_3()

# Report
count = 0
for user_resources in users_list:
    # tuple with user's resources before and after deletion.
    u_id = user_resources.user_id
    count += 1
    resources_before = report[u_id]
    try:
        msg = "Retrieving after resources of user: {0} ({1}/{2})"
        logger.info(msg.format(u_id, count, total))
        resources_after = user_resources.get_resources_dict()
    except Exception, e:
        msg = 'Error retrieving resources after freeing of user {0} cause: {1}'
        logger.error(msg.format(u_id, str(e)))
        # At least, save the resources before
        report[u_id] = (resources_before, resources_before, False)
        continue
    all_free = True
    for key in resources_after.keys():
        if resources_after[key]:
            all_free = False
            break
    report[u_id] = (resources_before, resources_after, all_free)
    for key in resources_before.keys():
        removed = len(resources_before[key]) - len(resources_after[key])
        if removed:
            total_free[key] = total_free.get(key, 0) + removed

# Save report

now = datetime.datetime.now().isoformat()
with open('freeresources_report_' + now + '.pickle', 'wf') as f:
    pickle.dump(report, f, protocol=-1)

logger.info('Resources freed: ' + str(total_free))

# Free trust_id tokes, if used
if free_trust_id:
    for user_resources in users_list:
        try:
            user_resources.free_trust_id()
        except Exception, e:
            msg = 'Error freeing trust_id of user {0}. Cause: {1}'
            logger.error(msg.format(user_resources.user_id, str(e)))
