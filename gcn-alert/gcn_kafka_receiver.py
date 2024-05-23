#!/usr/bin/env python
from ovro_alert import alert_client
from gcn_kafka import Consumer
from datetime import datetime, timedelta
from os import environ
import sys
import logging
import json
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

gc = alert_client.AlertClient('gcn')

logger = logging.getLogger(__name__)
logHandler = logging.StreamHandler(sys.stdout)
logFormat = logging.Formatter('%(asctime)s [%(levelname)-8s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logHandler.setFormatter(logFormat)
logger.addHandler(logHandler)
logger.setLevel(logging.DEBUG)

client_id = environ.get("GCN_KAFKA_CLIENT_ID")
client_secret = environ.get("GCN_KAFKA_CLIENT_SECRET")

if not client_id or not client_secret:
    logger.error("GCN_KAFKA_CLIENT_ID and GCN_KAFKA_CLIENT_SECRET must be set in the environment.")
    sys.exit(1)

slack_token = environ.get("SLACK_TOKEN_CR")
slack_channel = "#alert-driven-astro"  
send_to_slack = bool(slack_token)

if slack_token:
    slack_client = WebClient(token=slack_token)
    logger.debug("Created Slack client")

consumer = Consumer(client_id=client_id, client_secret=client_secret)

# Add 'gcn.notices.einstein_probe.wxt.alert' later? 
# example of received json can be found here https://github.com/nasa-gcn/gcn-schema/blob/v4.0.0/gcn/notices/einstein_probe/wxt/alert.schema.example.json
consumer.subscribe(['gcn.notices.swift.bat.guano'])  


def post_to_slack(channel, message):
    """Post a message to a Slack channel."""
    try:
        response = slack_client.chat_postMessage(channel=channel, text=message)
    except SlackApiError as e:
        logger.error(f"Error sending to Slack: {e.response['error']}")

while True:
    for message in consumer.consume(timeout=1):
        if message.error():
            logger.error(message.error())
            continue

        try:
            alert = json.loads(message.value().decode('utf-8'))
            
            rate_duration = alert["rate_duration"]
            event_time = datetime.strptime(alert["trigger_time"], '%Y-%m-%dT%H:%M:%S.%fZ')
            current_time = datetime.utcnow()

            if (
                rate_duration < 2 
                and (current_time - event_time) < timedelta(minutes=10)
                and "ra" in alert
                and "dec" in alert
                and "radius" in alert
            ):
                logger.info(f'Event at {alert["alert_datetime"]}: RA, Dec = ({alert["ra"]}, {alert["dec"]}, radius={alert["radius"]}).')
                logger.info(f'Rate_duration: {rate_duration}. Rate_snr: {alert["rate_snr"]}.')

                # duration is set to one hour
                args = args = {
                    'duration': 3600, 
                    'position': f'{alert["ra"]},{alert["dec"]},{alert["radius"]}',
                    'instrument': alert["instrument"],
                    'mission': alert["mission"]
                }
                gc.set('gcn', args)

                message = (
                    f"Swift/BAT-GUANO Alert: RA, Dec = ({alert['ra']}, {alert['dec']}, radius={alert['radius']}).\n"
                    f"Rate_duration: {rate_duration}. Rate_snr: {alert['rate_snr']}.\n"
                    f"Instrument: {alert['instrument']}. Mission: {alert['mission']}."
                )
                if send_to_slack:
                    post_to_slack(slack_channel, message)

        except Exception as e:
            logger.error(f'Error processing message: {e}')
