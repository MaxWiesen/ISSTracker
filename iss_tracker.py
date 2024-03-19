import requests
import datetime
import math
import pandas as pd
import numpy as np
from flask import Flask, request
from lxml import etree
from geopy.geocoders import Nominatim
app = Flask(__name__)


def get_data(url: str) -> pd.DataFrame:
    '''
    Function to retrieve and preprocess NASA Data from a given URL (assuming it matches format).

    Parameters
    ----------
    url     str             indicates which URL to retrieve NASA data from

    Returns
    -------
    df      pd.DataFrame    Dataframe containing parsed and preprocessed NASA data
    '''
    if url.rsplit('.')[-1] != 'xml':
        raise ValueError('URL does not path to an XML file.')

    df = pd.read_xml(requests.get(url).text,
                     xpath='/ndm/oem[@id="CCSDS_OEM_VERS"]/body/segment/data/stateVector/*').drop('units', axis=1)
    df = pd.DataFrame({col: df[col].shift(-ind) for ind, col in enumerate(df.columns)}).dropna().reset_index(drop=True)
    df.index = pd.to_datetime(df['EPOCH'], format='%Y-%jT%H:%M:%S.%fZ')
    return df


def format_return(df_of_one: pd.DataFrame) -> dict:
    return {col: val[0] for col, val in df_of_one.to_dict('list').items()}


@app.route('/comment', methods=['GET'])
def get_comment():
    '''
    Function to retrieve and return comment objects from NASA data

    Returns
    -------
    string      containing all comments from NASA data as a formatted string
    '''
    df = etree.fromstring(requests.get('https://nasa-public-data.s3.amazonaws.com/iss-coords/current/ISS_OEM/ISS.OEM_J2K_EPH.xml').content)
    return '\n'.join([line.text if line.text else '\n' for line in df.xpath('/ndm/oem[@id="CCSDS_OEM_VERS"]/body/segment/data/COMMENT')]) + '\n'


@app.route('/header', methods=['GET'])
def get_header():
    '''
    Function to retrieve and return contents of header object from NASA data

    Returns
    -------
    dict        containing all tags and information of the contents of the header object
    '''
    df = etree.fromstring(requests.get('https://nasa-public-data.s3.amazonaws.com/iss-coords/current/ISS_OEM/ISS.OEM_J2K_EPH.xml').content)
    return {element.tag: element.text for element in df.xpath('/ndm/oem[@id="CCSDS_OEM_VERS"]/header/*')}


@app.route('/metadata', methods=['GET'])
def get_metadata():
    '''
    Function to retrieve and return contents of metadata object from NASA data

    Returns
    -------
    dict        containing all tags and information of the contents of the header object
    '''
    df = etree.fromstring(requests.get('https://nasa-public-data.s3.amazonaws.com/iss-coords/current/ISS_OEM/ISS.OEM_J2K_EPH.xml').content)
    return {element.tag: element.text for element in df.xpath('/ndm/oem[@id="CCSDS_OEM_VERS"]/body/segment/metadata/*')}


@app.route('/epochs', methods=['GET'])
def get_epochs():
    '''
    Route to get all data from the dataset, with the option to send query parameter to limit or offset the data return
    from the original dataset

    Returns
    -------
    dict        containing data with offset or entire dataset
    '''
    df = get_data('https://nasa-public-data.s3.amazonaws.com/iss-coords/current/ISS_OEM/ISS.OEM_J2K_EPH.xml')
    offset = request.args.get('offset', 0)
    limit = request.args.get('limit', -1)
    if offset != 0 and offset.isnumeric() and int(offset) > len(df):
        return 'Error: Offset cannot be greater than length of records.\n'
    try:
        if int(offset) < 0 and abs(int(offset)) > len(df):
            return 'Error: Absolute value of offset must not be great than length of records.\n'
    except ValueError:
        return 'Error: Could not convert offset to a number.\n'

    try:
        if int(offset) < 0 and int(limit) + int(offset) > 0:
            return 'Error: Limit must be less than the absolute value of offset when offset is negative.\n'
    except ValueError:
        return 'Error: Could not convert limit to a number.\n'

    if limit == -1 or (limit.isnumeric() and ((int(offset) + int(limit) > len(df) or (int(offset) < 0 and int(offset) + int(limit) > 0)) if offset else int(limit) > len(df))):
        return df.iloc[int(offset):].to_dict('list')
    return df.iloc[int(offset):int(offset) + int(limit)].to_dict('list')


@app.route('/epochs/<epoch_in>', methods=['GET'])
def get_epoch(epoch_in):
    '''
    Route to return information about an individual epoch.

    Parameters
    ----------
    epoch_in    ISO8601 formatted epoch string

    Returns
    -------
    dict        all information about the given epoch
    '''
    df = get_data('https://nasa-public-data.s3.amazonaws.com/iss-coords/current/ISS_OEM/ISS.OEM_J2K_EPH.xml')
    try:
        return format_return(df.loc[df['EPOCH'] == epoch_in])
    except IndexError:
        return f'Error: Epoch {epoch_in} not found.\n'


@app.route('/epochs/<epoch_in>/speed', methods=['GET'])
def get_epoch_speed(epoch_in):
    '''
    Route to get speed at a given epoch

    Parameters
    ----------
    epoch_in    ISO8601 formatted epoch string

    Returns
    -------
    dict        speed at given epoch
    '''
    df = get_data('https://nasa-public-data.s3.amazonaws.com/iss-coords/current/ISS_OEM/ISS.OEM_J2K_EPH.xml')
    try:
        epoch = format_return(df.loc[df['EPOCH'] == epoch_in])
        return {'speed': np.sqrt(
            epoch['X_DOT'] * epoch['X_DOT'] + epoch['Y_DOT'] * epoch['Y_DOT'] + epoch['Z_DOT'] * epoch['Z_DOT'])}
    except IndexError:
        return f'Error: Epoch {epoch_in} not found.\n'


def location_from_record(epoch):
    RADIUS_OF_EARTH = 6378137.0
    return_data = {}
    return_data['longitude'] = math.degrees(math.atan2(epoch['Y'], epoch['X'])) - (
                (int(epoch['EPOCH'].split('T')[-1][:2]) - 12) + (
                    float(epoch['EPOCH'].split('T')[-1][3:5]) / 60)) * 360 / 24 + 19
    if return_data['longitude'] > 180:
        return_data['longitude'] = -180 + (return_data['longitude'] - 180)
    elif return_data['longitude'] < -180:
        return_data['longitude'] = 180 + (return_data['longitude'] + 180)
    return_data['latitude'] = math.degrees(math.atan2(epoch['Z'], math.sqrt(epoch['Z'] ** 2 + epoch['Y'] ** 2)))
    return_data['altitude'] = math.sqrt(epoch['Z'] ** 2 + epoch['Y'] ** 2 + epoch['Z'] ** 2) - RADIUS_OF_EARTH

    geolocator = Nominatim(user_agent="iss_tracker")
    return_data['geoloc'] = geolocator.reverse(f"{return_data['latitude']}, {return_data['longitude']}", zoom=15,
                                               language='en')
    if return_data['geoloc'] is None:
        return_data['geoloc'] = 'Nearest city unavailable - perhaps over ocean'
    else:
        return_data['geoloc'] = return_data['geoloc'].address
    return return_data


@app.route('/epochs/<epoch_in>/location', methods=['GET'])
def get_location(epoch_in):
    '''
    Route to get information about the location at a given epoch using cartesian to geodetic algorithms for Earth.
    Also includes the name of the nearest city recognized using GeoPy

    Parameters
    ----------
    epoch_in    ISO8601 formatted epoch string

    Returns
    -------
    dict        information about location at given epoch
    '''
    try:
        df = get_data('https://nasa-public-data.s3.amazonaws.com/iss-coords/current/ISS_OEM/ISS.OEM_J2K_EPH.xml')
        epoch = format_return(df.loc[df['EPOCH'] == epoch_in])
    except IndexError:
        return f'Error: Epoch {epoch_in} not found.\n'

    return location_from_record(epoch)


@app.route('/now', methods=['GET'])
def get_recent():
    '''
    Route to get most recent epoch to the current time.

    Returns
    -------
    dict        all information about the most recent epoch
    '''
    df = get_data('https://nasa-public-data.s3.amazonaws.com/iss-coords/current/ISS_OEM/ISS.OEM_J2K_EPH.xml')
    df['timedelta'] = datetime.datetime.now() - df.index
    epoch = format_return(df.loc[df.timedelta == df.timedelta.min()])
    del epoch['timedelta']
    return_payload = location_from_record(epoch)
    return_payload['epoch'] = epoch['EPOCH']
    return_payload['speed'] = np.sqrt(epoch['X_DOT'] * epoch['X_DOT'] + epoch['Y_DOT'] * epoch['Y_DOT'] + epoch['Z_DOT'] * epoch['Z_DOT'])
    return return_payload


def main():
    app.run(host='0.0.0.0')


if __name__ == '__main__':
    main()
