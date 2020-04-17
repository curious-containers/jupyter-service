import copy
import uuid

import requests
from werkzeug.urls import url_fix, url_join

from cc_jupyter_service.common import red_file_template
from cc_jupyter_service.service.db import get_db


def get_notebook():
    """
    Returns the requested notebook data.

    :return:
    """


def normalize_url(url):
    """
    Adds https:// at the begin and / at the end if missing.

    :param url: The url to fix
    :type url: str
    :return: The fixed url
    :rtype: str
    """
    url = url_fix(url)
    if not (url.startswith('https://') or url.startswith('http://')):
        url = 'https://' + url
    if not url.endswith('/'):
        url = url + '/'
    return url


def check_agency(agency_url, agency_username, agency_password):
    """
    Tries to contact the agency with the given authorization information. Raises a AgencyError, if the agency is not
    available or the authentication information is invalid.

    :param agency_url: The agency to contact
    :type agency_url: str
    :param agency_username: The username to use for authorization
    :type agency_username: str
    :param agency_password: The password to use for authorization
    :type agency_password: str

    :raise AgencyError: If the agency is not available or authentication information is invalid.
    """
    agency_url = url_join(agency_url, 'nodes')
    response = None
    try:
        response = requests.get(agency_url, auth=(agency_username, agency_password))
        response.raise_for_status()
    except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError) as e:
        if response is not None:
            raise AgencyError(
                'Failed to verify agency "{}" for user "{}".\nstatus code: {}\nmessage: {}'.format(
                    agency_url, agency_username, response.status_code, str(e)
                )
            )
        else:
            raise AgencyError(
                'Failed to verify agency "{}" for user "{}".\nmessage: {}'.format(agency_url, agency_username, str(e))
            )


def exec_notebook(notebook_data, agency_url, agency_username, agency_password, notebook_database, url_root):
    """
    - Validates the agency authentication information
    - Generates a new id and token for the notebook
    - Saves the notebook
    - Saves meta information in the db
    - Executes the notebook on the agency

    :param notebook_data: The notebook data given as dictionary to execute.
    :param agency_url: The agency to use for execution
    :type agency_url: str
    :param agency_username: The agency username to use
    :type agency_username: str
    :param agency_password: The password for the given agency user
    :type agency_password: str
    :param notebook_database: The notebook database to save the notebook in
    :type notebook_database: NotebookDatabase
    :param url_root: The url root of this notebook service
    :type url_root: str

    :return: The experiment id of the executed experiment
    :rtype: str
    """
    agency_url = normalize_url(agency_url)

    check_agency(agency_url, agency_username, agency_password)

    notebook_id = uuid.uuid4()

    notebook_token = uuid.uuid4()
    notebook_database.save_notebook(notebook_data, notebook_id)

    db = get_db()
    db.execute(
        'INSERT INTO notebook (notebook_id, token, username, agencyurl) VALUES (?, ?, ?, ?)',
        (str(notebook_id), str(notebook_token), agency_username, agency_url)
    )
    db.commit()

    return start_agency(notebook_id, notebook_token, agency_url, agency_username, agency_password, url_root)


def _create_red_data(notebook_id, notebook_token, agency_url, agency_username, agency_password, url_root):
    """
    Creates the red data that can be used for execution on an agency.

    :param notebook_id: The token to reference the notebook.
    :type notebook_id: uuid.UUID
    :param notebook_token: The token to authorize the notebook.
    :type notebook_token: uuid.UUID
    :param agency_url: The agency to use for execution
    :type agency_url: str
    :param agency_username: The agency username to use
    :type agency_username: str
    :param agency_password: The password for the given agency user
    :type agency_password: str
    :param url_root: The url root of this notebook service
    :type url_root: str
    :return: The red data filled with the given information to execute on an agency
    """
    red_data = copy.deepcopy(red_file_template.RED_FILE_TEMPLATE)

    # input notebook
    input_notebook_access = red_data['inputs']['inputNotebook']['connector']['access']
    input_notebook_access['url'] = url_join(url_root, 'notebook/' + str(notebook_id))
    input_notebook_access['auth']['username'] = agency_username
    input_notebook_access['auth']['password'] = str(notebook_token)

    # output notebook
    output_notebook_access = red_data['outputs']['outputNotebook']['connector']['access']
    output_notebook_access['url'] = url_join(url_root, 'notebook/' + str(notebook_id))
    output_notebook_access['auth']['username'] = agency_username
    output_notebook_access['auth']['password'] = str(notebook_token)

    # execution engine
    execution_engine_access = red_data['execution']['settings']['access']
    execution_engine_access['url'] = agency_url
    execution_engine_access['auth']['username'] = agency_username
    execution_engine_access['auth']['password'] = agency_password

    return red_data


def start_agency(notebook_id, notebook_token, agency_url, agency_username, agency_password, url_root):
    """
    Executes the given notebook on the given agency.

    :param notebook_id: The id to reference the notebook.
    :type notebook_id: uuid.UUID
    :param notebook_token: The token to authorize the notebook.
    :type notebook_token: uuid.UUID
    :param agency_url: The agency to use for execution
    :type agency_url: str
    :param agency_username: The agency username to use
    :type agency_username: str
    :param agency_password: The password for the given agency user
    :type agency_password: str
    :param url_root: The url root of this notebook service
    :type url_root: str

    :return: The experiment id of the started experiment
    :rtype: str

    :raise HTTPError: If the red post failed
    """
    red_data = _create_red_data(notebook_id, notebook_token, agency_url, agency_username, agency_password, url_root)

    r = requests.post(
        url_join(agency_url, 'red'),
        auth=(agency_username, agency_password),
        json=red_data
    )

    r.raise_for_status()

    return r.json()['experimentId']


class AgencyError(Exception):
    pass
