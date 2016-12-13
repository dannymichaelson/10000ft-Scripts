#!/usr/bin/python3
import datetime
import json
import logging
import requests

import constants


logging.basicConfig(filename='exceptions.log',
                    format='%(asctime)s.%(msecs)d %(levelname)s %(module)s - %(funcName)s: %(message)s',
                    datefmt="%Y-%m-%d %H:%M:%S")

projects_list = None


def update_10k_project(client_name, project_name, start_date, end_date):
	global projects_list
	if projects_list is None:
		params = {
			'auth': constants.API_KEY_10K,
			'sort_field': 'updated',
			'sort_order': 'descending',
			'per_page': 250
		}
		resp = requests.get(constants.API_BASE_URL_10K + '/projects', params=params)
		if resp.status_code != 200:
	        # Something went wrong, log and go to the next sheet
			logging.warning('GET /projects/ {}'.format(resp.status_code))
			return None
		projects_list = resp.json()['data']
	#print(projects_list)
	for project in projects_list:
		if project['client'] is None or project['name'] is None:
			return
		if project['client'].lower() == client_name.lower() and project['name'].lower() == project_name.lower():
			if project['starts_at'] != start_date or project['ends_at'] != end_date:
				#print('updating', client_name, project_name)
				params = {
					'auth': constants.API_KEY_10K,
					'id': project['id'],
					'starts_at': start_date,
					'ends_at': end_date
				}
				resp = requests.put(constants.API_BASE_URL_10K + '/projects/' + str(project['id']), params=params)
				if resp.status_code != 200:
			        # Something went wrong, log and go to the next sheet
					logging.warning('PUT /projects/{} {}'.format(project['id'], resp.status_code))
				#print(resp.json())




def get_date(sheet, headers, start=False, end=False):
	'''Returns the start or end date from the sheet. Choose only start XOR end to look for'''
	sheet_id = sheet['id']
	if start == end:
		return

	cell_keyword = constants.SMARTSHEET_START_TEXT if start else constants.SMARTSHEET_END_TEXT
	column_keyword = constants.SMARTSHEET_START_COLUMN if start else constants.SMARTSHEET_END_COLUMN

	# Try to find one occurance of our start date keyword
	resp = requests.get(constants.API_BASE_URL_SMARTSHEET + '/search/sheets/' + str(sheet_id) + '?query=' + cell_keyword, headers=headers)
	if resp.status_code != 200:
        # Something went wrong, log and go to the next sheet
		logging.warning('GET /search/sheets/{}?query={} {}'.format(sheet_id, cell_keyword, resp.status_code))
		return None

	# If we didn't find the keyword, or we found multiple (don't know how to handle this), go to the next sheet
	if resp.json()['totalCount'] is not 1:
		logging.warning('Searching sheet {} for {} - {} found'.format(sheet['name'], cell_keyword, resp.json()['totalCount']))
		return None

	# Get the ID of the row where the start date keyword was found
	row_id = resp.json()['results'][0]['objectId']

	# Include columns so we know whats what. Exclude cells that have never had values to make our search faster
	params = {
		'include': 'columns',
		'exclude': 'nonexistentCells'
	}
	resp = requests.get(constants.API_BASE_URL_SMARTSHEET + '/sheets/' + str(sheet_id) + '/rows/' + str(row_id), params=params, headers=headers)
	if resp.status_code != 200:
		logging.warning('GET /sheets/{}/rows/{} {}'.format(sheet_id, row_id, resp.status_code))
		return None

	data = resp.json()
	columns = data['columns']
	cells = data['cells']
	# Look through each column to find start/end keyword
	for column in columns:
		if column['title'].lower() == column_keyword.lower():
			# We found it, so lets look for a cell with a matching columnId
			for cell in cells:
				if cell['columnId'] == column['id']:
					# columnId matched, this is the date in YYYY-MM-DDTHH:MM:SS so split on the 'T' to just return the date
					return cell['value'].split('T')[0]
	# No matches
	return None



def get_sheet_list():
	headers = {
		'Authorization': 'Bearer ' + constants.API_KEY_SMARTSHEET
	}
	params = {
		'includeAll': True
	}
	resp = requests.get(constants.API_BASE_URL_SMARTSHEET + '/users/sheets', params=params, headers=headers)
	if resp.status_code != 200:
        # Something went wrong listing all sheets, abort
		logging.error('GET /users/sheets/ {}'.format(resp.status_code))
		return

	sheets_list = resp.json()['data']
	#print(sheets_list)
	return sheets_list

	



def main():

	sheets_list = get_sheet_list()
	for sheet in sheets_list:
		#print(sheet)
		# We have to assume the owner's identity to access the sheet
		# Following the 'fetch each sheet' code sample from http://smartsheet-platform.github.io/api-docs/?shell#backup-all-org-data
		headers = {
			'Authorization': 'Bearer ' + constants.API_KEY_SMARTSHEET,
			'Assume-User': sheet['owner']
		}
		#Split sheet name ("Client Name: Project Name") into client name and project name
		split_name = sheet['name'].split(':')
		# Skip this sheet if name is not formatted how we want
		if len(split_name) is not 2:
			continue
		# Client name comes first
		client_name = split_name[0].strip()
		# Followed by the project name
		project_name = split_name[1].strip()
		sheet_id = sheet['id']
		start_date = get_date(sheet, headers, start=True)
		# Skip this sheet if we didnt find a start date
		if start_date is None:
			logging.warning(sheet['name'] + " start not found")
			continue
		end_date = get_date(sheet, headers, end=True)
		# Skip this sheet if we didnt find an end date
		if end_date is None:
			logging.warning(sheet['name'] + " end not found")
			continue

		update_10k_project(client_name, project_name, start_date, end_date)

		#print(client_name, project_name, start_date, end_date)


if __name__ == '__main__':
    main()
