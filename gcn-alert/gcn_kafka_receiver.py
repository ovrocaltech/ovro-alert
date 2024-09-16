#!/usr/bin/env python
import os
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

logger.debug(f"GCN_KAFKA_CLIENT_ID: {os.getenv('GCN_KAFKA_CLIENT_ID')}")
logger.debug(f"GCN_KAFKA_CLIENT_SECRET: {os.getenv('GCN_KAFKA_CLIENT_SECRET')}")

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

# Connect as a consumer
consumer = Consumer(client_id=client_id, client_secret=client_secret)

# Subscribe to both the Swift and Einstein Probe alert topics
consumer.subscribe(['gcn.notices.swift.bat.guano', 'gcn.notices.einstein_probe.wxt.alert'])

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
            logger.debug(f'Received message: {message.value().decode("utf-8")}')
            alert = json.loads(message.value().decode('utf-8'))
            
            rate_duration = alert.get("rate_duration", None)
            event_time_str = alert.get("trigger_time", None)
            #event_time = datetime.strptime(event_time_str, '%Y-%m-%dT%H:%M:%S.%fZ') if event_time_str else None
            #current_time = datetime.utcnow()

            if (
                rate_duration is not None 
                #and event_time is not None
                and rate_duration < 2
                #and (current_time - event_time) < timedelta(minutes=10)
                and "ra" in alert
                and "dec" in alert
                and "radius" in alert
            ):
                logger.info(f'Event at {alert["trigger_time"]}: RA, Dec = ({alert["ra"]}, {alert["dec"]}, radius={alert["radius"]}).')
                logger.info(f'Rate_duration: {rate_duration}. Rate_snr: {alert["rate_snr"]}.')

                # duration is set to one hour
                args = {
                    'duration': 3600, 
                    'position': f'{alert["ra"]},{alert["dec"]},{alert["radius"]}',
                    'instrument': alert["instrument"],
                    'mission': alert["mission"]
                }
                gc.set('gcn', args)

                message = (
                    f"GCN alert: Instrument: {alert['instrument']}. Mission: {alert['mission']}.\n"
                    f"RA, Dec = ({alert['ra']}, {alert['dec']}, radius={alert['radius']}).\n"
                    f"Rate_duration: {rate_duration}. Rate_snr: {alert['rate_snr']}."
                )
                if send_to_slack:
                    post_to_slack(slack_channel, message)
            elif (
                "ra" in alert
                and "dec" in alert
                and "ra_dec_error" in alert
                and "net_count_rate" in alert
                and "image_snr" in alert
                #and event_time is not None
                #and (current_time - event_time) < timedelta(minutes=10)
                and alert["image_snr"] > 3
            ):
                logger.info(f'Event at {alert["trigger_time"]}: RA, Dec = ({alert["ra"]}, {alert["dec"]}, ra_dec_error={alert["ra_dec_error"]}).')
                logger.info(f'Net count rate: {alert["net_count_rate"]}. Image SNR: {alert["image_snr"]}.')

                # duration is set to one hour
                args = {
                    'duration': 3600, 
                    'position': f'{alert["ra"]},{alert["dec"]},{alert["ra_dec_error"]}',
                    'instrument': alert["instrument"],
                    'mission': alert.get("mission", "Unknown")
                }
                gc.set('gcn', args)

                message = (
                    f"GCN alert: Instrument: {alert['instrument']}.\n"
                    f"RA, Dec = ({alert['ra']}, {alert['dec']}, ra_dec_error={alert['ra_dec_error']}).\n"
                    f"Net count rate: {alert['net_count_rate']}. Image SNR: {alert['image_snr']}."
                )
                if send_to_slack:
                    post_to_slack(slack_channel, message)

        except Exception as e:
            logger.error(f'Error processing message: {e}')
