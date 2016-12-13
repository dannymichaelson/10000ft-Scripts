#!/usr/bin/python3

from __future__ import print_function
from contextlib import closing

import datetime
import httplib2
import logging
import os
import requests
import shelve

from apiclient import discovery
import oauth2client
from oauth2client import client
from oauth2client import tools

import constants

logging.basicConfig(filename='exceptions.log',
                    format='%(asctime)s.%(msecs)d %(levelname)s %(module)s - %(funcName)s: %(message)s',
                    datefmt="%Y-%m-%d %H:%M:%S")

try:
    import argparse
    parser = argparse.ArgumentParser(parents=[tools.argparser])
    parser.add_argument("-i", "--initial", help="Initial run. Adds all events to time off if they don't already exist.",
                        action="store_true")
    parser.add_argument("-n", "--nuke", help="Nuke our database", action="store_true")
    flags = parser.parse_args()
except ImportError:
    flags = None

# If modifying these scopes, delete your previously saved credentials
# at .credentials/calendar-python-quickstart.json in the CWD
SCOPES = 'https://www.googleapis.com/auth/calendar.readonly'
CLIENT_SECRET_FILE = os.path.join(os.getcwd(), 'client_secret.json')
APPLICATION_NAME = "10k' Sync"

# Global variables used during runtime
users_disp_name_to_id = None
leave_types_dict = None
sync_token = None
gcal_to_10k_dict = {}
todays_date = datetime.datetime.utcnow().isoformat().split("T")[0]
error_flag = False


def nuke():
    global gcal_to_10k_dict

    with closing(shelve.open('shelf')) as shelf:
        if 'gcal_to_10k' in shelf:
            gcal_to_10k_dict = shelf['gcal_to_10k']
            for key in shelf['gcal_to_10k']:
                #print("deleting", key)
                delete_10k_assignment(key)
        shelf['gcal_to_10k'] = {}
        shelf['sync_token'] = None
        shelf['last_purge'] = ''


def get_gcal_credentials():
    """Taken from Google's Calendar API Quickstart
      https://developers.google.com/google-apps/calendar/quickstart/python
      Moved location of credentials from home folder to working directory

      Gets valid user credentials from storage.

      If nothing has been stored, or if the stored credentials are invalid,
      the OAuth2 flow is completed to obtain the new credentials.

      Returns:
          Credentials, the obtained credential.
      """
    credential_dir = os.path.join(os.getcwd(), '.credentials')
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir,
                                   'calendar-python-quickstart.json')

    store = oauth2client.file.Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        if flags:
            credentials = tools.run_flow(flow, store, flags)
        else:  # Needed only for compatibility with Python 2.6
            credentials = tools.run(flow, store)
        #print('Storing credentials to ' + credential_path)
    return credentials


def get_10k_users_ids_dict():
    """Returns a dictionary mapping 10k' display names to their ids.
    """
    global users_disp_name_to_id

    #print("getting 10k users list")
    # Don't keep making requests. The users_list is cached the first time this function is called each run.
    if users_disp_name_to_id:
        return users_disp_name_to_id

    #print("syncing users list from 10k")
    # Parameters to send with the request. Our auth key and the number of users to return.
    params = {
        'auth': constants.API_KEY_10K,
        'per_page': constants.NUMBER_OF_10K_USERS,
    }
    # Make the request
    resp = requests.get(constants.API_BASE_URL_10K + '/users', params=params)
    if resp.status_code != 200:
        # Something went wrong
        logging.error('Unable to GET /users {}'.format(resp.status_code))
        raise Exception('Unable to GET /users {}'.format(resp.status_code))

    # Store our data. Don't care about pagination since users per page >= number of users
    users_list = resp.json()['data']
    users_disp_name_to_id = {}
    for user in users_list:
        users_disp_name_to_id[user['display_name'].lower()] = user['id']

    #print(users_disp_name_to_id)
    return users_disp_name_to_id


def get_10k_user_id(display_name):
    """Returns the 10K' user id for the given display name
    :param display_name: Full name as it appears in 10K'
    :return: The id of the user or None
    """
    display_name = display_name.lower()
    users_ids = get_10k_users_ids_dict()
    if display_name in users_ids:
        return users_ids[display_name]
    return None


def get_10k_leave_types():
    global leave_types_dict

    if leave_types_dict:
        return leave_types_dict
    else:
        leave_types_dict = {}

    #print("Getting leave types list")

    params = {
        'auth': constants.API_KEY_10K,
    }
    resp = requests.get(constants.API_BASE_URL_10K + '/leave_types', params=params)
    if resp.status_code != 200:
        # Something went wrong
        logging.error('GET /leave_types {}'.format(resp.status_code))
        raise Exception('GET /leave_types {}'.format(resp.status_code))

    leave_types_list = resp.json()['data']
    for leave_type in leave_types_list:
        leave_types_dict[leave_type['name'].lower()] = leave_type['id']

    #print(leave_types_dict)
    return leave_types_dict


def get_10k_leave_id(leave_reason):
    leave_types = get_10k_leave_types()
    if leave_reason.lower() in leave_types:
        return leave_types[leave_reason.lower()]
    return None


def create_10k_assignment(user_id, leave_id, start_date, end_date, gcal_event_id):
    """Create a new assignment for user with id user_id.
    user_id: the id of the user who we are adding an assignment to
    leave_id: the id of the leave type to be assigned
    start_date: Start time off
    end_date: End time off

    Returns:
    JSON object of successfully created evento
    """
    params = {
        'auth': constants.API_KEY_10K,
        'leave_id': leave_id,
        'starts_at': start_date,
        'ends_at': end_date
    }


    resp = requests.post(constants.API_BASE_URL_10K + '/users/' + str(user_id) + '/assignments', params=params)
    if resp.status_code != 200:
        # Something went wrong
        logging.warning('POST /users/' + user_id + '/assignments {}'.format(resp.status_code))
        error_flag = True

    assignment = resp.json()

    gcal_to_10k_dict[gcal_event_id] = {
        '10k_id': assignment['id'],
        'user_id': assignment['user_id'],
        'start_date': start_date,
        'end_date': end_date
    }
    #print("created event")

    return assignment


def update_10k_assignment(user_id, event_id, start_date, end_date, gcal_event_id):
    global gcal_to_10k_dict

    params = {
        'auth': constants.API_KEY_10K,
        'starts_at': start_date,
        'ends_at': end_date
    }

    resp = requests.put(constants.API_BASE_URL_10K + '/users/' + str(user_id) + '/assignments/' + str(event_id), params=params)
    if resp.status_code != 200:
        # Something went wrong
        logging.warning('POST /users/' + user_id + '/assignments/' + event_id + ' {}'.format(resp.status_code))
        error_flag = True

    assignment = resp.json()

    gcal_to_10k_dict[gcal_event_id] = {
        '10k_id': assignment['id'],
        'user_id': assignment['user_id'],
        'start_date': start_date,
        'end_date': end_date
    }


def delete_10k_assignment(gcal_event_id):
    global gcal_to_10k_dict
    #print("delete_10k_assignment", "'" + gcal_event_id + "'")
    if gcal_event_id not in gcal_to_10k_dict:
        #print(gcal_to_10k_dict)
        #print(gcal_event_id + " not found")
        return

    params = {
        'auth': constants.API_KEY_10K,
    }

    event_id = gcal_to_10k_dict[gcal_event_id]['10k_id']
    user_id = gcal_to_10k_dict[gcal_event_id]['user_id']
    #print(constants.API_BASE_URL_10K + '/users/' + str(user_id) + '/assignments/' + str(event_id))
    resp = requests.delete(constants.API_BASE_URL_10K + '/users/' + str(user_id) + '/assignments/' + str(event_id), params=params)
    if resp.status_code != 200:
        # Something went wrong
        logging.warning('DELETE /users/' + str(user_id) + '/assignments/' + str(event_id) + '{}'.format(resp.status_code))
        error_flag = True
    else:
        gcal_to_10k_dict.pop(gcal_event_id, 0)

    #print(resp)
    return


def gcal_sync(service, pageToken=None, initial=False):
    global sync_token 

    if initial:
        #print("Initial sync")
        # This should only get confirmed upcoming events
        try:
            eventsResult = service.events().list(
                            calendarId=constants.CALENDAR_ID, singleEvents=True, maxResults=2500).execute()
        except Exception as e:
            logging.exception(e)
            raise Exception(e)
    else:
        try:
            eventsResult = service.events().list(
                            calendarId=constants.CALENDAR_ID, singleEvents=True, syncToken=sync_token, maxResults=2500, pageToken=pageToken).execute()
        except Exception as e:
            logging.exception(e)
            raise Exception(e)
    events = eventsResult.get('items', [])
    next_page_token = eventsResult.get('nextPageToken')
    for event in events:
        if event['status'] == 'cancelled':
            delete_10k_assignment(event['id'])
        else:
            # Split summary (title) on "-": Display Name - Leave Type
            summary_split = event['summary'].split(constants.GCAL_SPLIT)
            if len(summary_split) is not 2:
                logging.warning("Invalid number of arguments in gcal title: {}".format(event['summary']))
                continue

            disp_name = summary_split[0].strip()
            leave_type = summary_split[1].strip()

            user_id = get_10k_user_id(disp_name)
            leave_id = get_10k_leave_id(leave_type)

            if user_id is None or leave_id is None:
                logging.warning("User or Leave id not found: user {}, leave {}, {}".format(user_id, leave_id, event['summary']))
                continue

            #print(event)

            # Split Datetime into Date and Time, only keep date
            if 'dateTime' in event['start']:
                start_date = event['start']['dateTime'].split("T")[0]
                end_date = event['end']['dateTime'].split("T")[0]
            else:
                start_date = event['start']['date']
                end_date = event['end']['date']

            #print(disp_name, start_date, end_date, leave_type, event['id'])

            if event['id'] in gcal_to_10k_dict:
                update_10k_assignment(user_id, gcal_to_10k_dict[event['id']]['10k_id'], start_date, end_date, event['id'])
            else:
                print(create_10k_assignment(user_id, leave_id, start_date, end_date, event['id']))

    sync_token = eventsResult.get('nextSyncToken')
    #print(sync_token, next_page_token)
    # Handling pagination uggggh - this probably isn't good
    if next_page_token:
        gcal_sync(service, pageToken=next_page_token, initial=False)


def purge_expired_events():
    global gcal_to_10k_dict
    #print(gcal_to_10k_dict)
    gcal_to_10k_dict = { k:v for k,v in gcal_to_10k_dict.items() if v['end_date'] >= todays_date }
    #print(gcal_to_10k_dict)
    return


def main():
    global sync_token
    global gcal_to_10k_dict

    # Clear our stored information if so desired
    if flags.nuke:
        nuke()

    # Open our storage 'shelf'
    with closing(shelve.open('shelf')) as shelf:
        if 'sync_token' in shelf:
            sync_token = shelf['sync_token']
            #print(sync_token)
        if 'gcal_to_10k' in shelf:
            gcal_to_10k_dict = shelf['gcal_to_10k']
            #print(gcal_to_10k_dict)

        # Initialize google calendar api
        credentials = get_gcal_credentials()
        http = credentials.authorize(httplib2.Http())
        service = discovery.build('calendar', 'v3', http=http)

        # Lets do it
        gcal_sync(service, initial=flags.initial)

        # Remove expired events once a day
        if 'last_purge' in shelf:
            if shelf['last_purge'] < todays_date:
                purge_expired_events()
                shelf['last_purge'] = todays_date
        else:
            purge_expired_events()
            shelf['last_purge'] = todays_date

        # Store our updated data for next time
        shelf['gcal_to_10k'] = gcal_to_10k_dict
        # If an API call went bad, we want to make sure we try again next time. Otherwise, update sync token
        if not error_flag:
            shelf['sync_token'] = sync_token


if __name__ == '__main__':
    main()
