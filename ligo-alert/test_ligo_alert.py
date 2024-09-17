import datetime
from ovro_alert import alert_client

# Example setup for the relay server connection
ligoc = alert_client.AlertClient('ligo')

# Create a datetime object with the current time in UTC
now = datetime.datetime.utcnow()

role = "observation"  # This is just an example role
example_params = {
    'FAR': '1.5e-3',  # Example FAR value
    'BNS': '0.9',  # Example BNS probability
    'HasNS': '0.8',  # Example HasNS probability
    'Terrestrial': '0.00',  # Example Terrestrial probability
    'GraceID': 'G12345678',  # Example Grace ID
    'AlertType': 'Initial'  # Example alert type
}

# Simulate sending the parameters to the relay server
try:
    ligoc.set(role, args={
        'FAR': example_params['FAR'],
        'BNS': example_params['BNS'],
        'HasNS': example_params['HasNS'],
        'Terrestrial': example_params['Terrestrial'],
        'GraceID': example_params['GraceID'],
        'AlertType': example_params['AlertType']
    })
    print(f"Alert sent successfully with parameters: {example_params}")
except Exception as e:
    print(f"Failed to send alert: {e}")

