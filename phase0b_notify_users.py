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
author = 'chema'

import requests
import logging
import warnings
import os.path
import cPickle as pickle
from requests.packages.urllib3.exceptions import InsecureRequestWarning

from osclients import osclients
from settings.settings import HORIZON_ENDPOINT

def notify_users(user_ids):
    """
    Notify users about the deletion of their resources sending an email to
    each one.
    :param user_ids: the list of user ids
    :return: nothing
    """
    filename = 'lastsession_yellow.pickle'
    user_ids_filtered = user_ids
    if os.path.exists(filename):
        with open(filename, 'rb') as f:
            previous = pickle.load(f)
            current = set()
            current.update(user_ids)
            user_ids_filtered = list(current - previous)

    logging.info('Notifying {0}/{1} users'.format(
        len(user_ids_filtered), len(user_ids)))

    if user_ids_filtered:
        body = {'users': user_ids_filtered}
        headers = {'X-Auth-Token': osclients.get_token()}

        horizon_url = HORIZON_ENDPOINT
        if horizon_url.endswith('/'):
            horizon_url = horizon_url[:-1]

        r = requests.post(horizon_url + '/notify_expire_users',
                          json=body, headers=headers, verify=False)
        if r.status_code not in (200, 204):
            msg = 'The operation returned code {0}: {1}'
            logging.error(msg.format(r.status_code, r.reason))
        else:
            # If there is an error with some users, they are
            # included in the body of the message.
            print 'Completed. ' + r.text

    # Replace file
    with open(filename, 'wf') as f:
        pickle.dump(user_ids, f, protocol=-1)


warnings.simplefilter('ignore', category=InsecureRequestWarning)
try:
    users = open('users_to_notify.txt')
except Exception:
    logging.error('The users_to_notify.txt file must exists')

list_users = list()
for line in users.readlines():
    user_id = line.strip()
    if user_id == '':
        continue
    list_users.append(user_id)

if list_users:
    notify_users(list_users)
