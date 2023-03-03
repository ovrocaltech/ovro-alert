import requests

ip = '131.215.200.144'  # major
port = '8000'
url = f'http://{ip}:{port}/lwa'

headers = {"Accept": "application/json"}

def get_lwa(password):
    """ 
    """

    resp = requests.get(url=url, headers=headers)
