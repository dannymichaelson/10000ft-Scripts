* gcal_to_10k.py: Retrieves a list of new/updated/cancelled events and makes the appropriate changes in 10k'

* smartsheet_to_10k.py: Looks at all smartsheets and if the Title matches 'Client Name: Project Name', syncs dates with the corresponding 10K' project.

* requirements.txt: A list of the required python packages. This is used when setting up on a new machine (pip install -r requirements.txt)

Create a constants.py file with the following variables

* constants.py: Important variables for accessing the APIs.
  - NUMBER_OF_10K_USERS: This number should be >= the number of 10k' user accounts
  - GCAL_SPLIT: The separator between name and OOO reason in a google calendar event
  - API_BASE_URL_10K: The base URL of the 10k' API
  - API_BASE_URL_SMARTSHEET: The base URL of the Smartsheet API
  - API_KEY_10K: The API key for a 10k' user with permission to schedule time
 				Find at: 10k' -> Settings -> Account Settings -> Developer API
  - API_KEY_SMARTSHEET: API key for Smartsheet Admin Account
 				Generated at: Smartsheet -> Account -> Personal Settings -> API Access
  - CALENDAR_ID: The Calendar ID of the desired OOO calendar
 				Find at: GCal -> Click the dropdown next to the calendar -> Calendar settings -> Calendar Address
  - SMARTSHEET_START_TEXT: The 'Task Name' that signals the start date of a project
  - SMARTSHEET_END_TEXT: The 'Task Name' that signals the end date of a project
  - SMARTSHEET_START_COLUMN: The title of the column that contains the Start date
  - SMARTSHEET_END_COLUMN: The title of the column that contaisn the End date