import os
from ovro_alert import alert_client
from gcn_kafka import Consumer
from datetime import datetime, timedelta
from os import environ
import sys
import logging
import json
from xml.etree import ElementTree
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

gc = alert_client.AlertClient('gcn')

logger = logging.getLogger(__name__)
logHandler = logging.StreamHandler(sys.stdout)
logFormat = logging.Formatter('%(asctime)s [%(levelname)-8s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logHandler.setFormatter(logFormat)
logger.addHandler(logHandler)
logger.setLevel(logging.DEBUG)

slack_channel = "#alert-driven-astro"


def _safe_float(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def parse_voevent(payload_text):
    """Parse a VOEvent XML payload into a dict of commonly used fields."""
    try:
        root = ElementTree.fromstring(payload_text)
    except ElementTree.ParseError:
        return None

    ns = {'voe': 'http://www.ivoa.net/xml/VOEvent/v2.0'}

    def find_text(path):
        elem = root.find(path, ns)
        return elem.text.strip() if elem is not None and elem.text else None

    # Debug: Log the XML structure
    logger.debug(f"VOEvent XML structure (first 1000 chars): {payload_text[:1000]}")

    # Try multiple XPath patterns for coordinates (Swift uses different structures)
    ra = (_safe_float(find_text('.//voe:WhereWhen//voe:Position2D//voe:Value2/voe:C1')) or
          _safe_float(find_text('.//voe:WhereWhen//voe:ObsDataLocation//voe:ObservationLocation//voe:AstroCoords//voe:Position2D//voe:Value2/voe:C1')))
    
    dec = (_safe_float(find_text('.//voe:WhereWhen//voe:Position2D//voe:Value2/voe:C2')) or
           _safe_float(find_text('.//voe:WhereWhen//voe:ObsDataLocation//voe:ObservationLocation//voe:AstroCoords//voe:Position2D//voe:Value2/voe:C2')))
    
    radius = (_safe_float(find_text('.//voe:WhereWhen//voe:Position2D/voe:Error2Radius')) or
              _safe_float(find_text('.//voe:WhereWhen//voe:ObsDataLocation//voe:ObservationLocation//voe:AstroCoords//voe:Position2D/voe:Error2Radius')))
    
    trigger_time = (find_text('.//voe:WhereWhen//voe:TimeInstant/voe:ISOTime') or
                    find_text('.//voe:WhereWhen//voe:ObsDataLocation//voe:ObservationLocation//voe:AstroCoords//voe:Time//voe:TimeInstant/voe:ISOTime'))
    
    logger.debug(f"Parsed coordinates: ra={ra}, dec={dec}, radius={radius}, trigger_time={trigger_time}")

    data = {
        'ra': ra,
        'dec': dec,
        'radius': radius,
        'trigger_time': trigger_time,
        'raw_format': 'voevent',
    }

    # Pull a few common params if they are present.
    for param in root.findall('.//voe:What/voe:Param', ns):
        name = (param.attrib.get('name') or '').lower()
        value = param.attrib.get('value') or (param.text.strip() if param.text else None)
        if not name or value is None:
            continue
        if name in ('instrument', 'mission'):
            data[name] = value
        elif name in ('rate_duration', 'rate_snr', 'image_snr', 'net_count_rate', 'ra_dec_error'):
            data[name] = _safe_float(value)

    # Remove keys with None values to avoid misleading downstream logic.
    return {k: v for k, v in data.items() if v is not None}


def parse_alert_payload(message_bytes):
    """Parse an alert payload that may be JSON, VOEvent XML, or plain text."""
    payload_text = message_bytes.decode('utf-8', errors='replace').strip()

    # Try JSON first.
    try:
        return json.loads(payload_text), 'json'
    except json.JSONDecodeError:
        pass

    # Try VOEvent XML.
    if payload_text.startswith('<'):
        voevent_data = parse_voevent(payload_text)
        if voevent_data is not None:
            return voevent_data, 'voevent'

    # Fallback: treat as plain text.
    return {'raw_text': payload_text, 'raw_format': 'text'}, 'text'


def parse_event_time(event_time_str):
    """Convert an ISO-like timestamp to a datetime, returning None on failure."""
    if not event_time_str:
        return None
    candidates = [
        '%Y-%m-%dT%H:%M:%S.%fZ',
        '%Y-%m-%dT%H:%M:%SZ',
        '%Y-%m-%dT%H:%M:%S',
    ]
    for fmt in candidates:
        try:
            return datetime.strptime(event_time_str, fmt)
        except ValueError:
            continue
    try:
        # Fall back to fromisoformat for odd-but-valid strings.
        clean = event_time_str.replace('Z', '+00:00')
        return datetime.fromisoformat(clean)
    except ValueError:
        logger.debug(f"Could not parse event_time: {event_time_str}")
        return None

def post_to_slack(channel, message, slack_client):
    """Post a message to a Slack channel."""
    try:
 #       response = slack_client.chat_postMessage(channel=channel, text=message)
        print(message)
    except SlackApiError as e:
        logger.error(f"Error sending to Slack: {e.response['error']}")


if __name__ == "__main__":
    logger.debug(f"GCN_KAFKA_CLIENT_ID: {os.getenv('GCN_KAFKA_CLIENT_ID')}")
    logger.debug(f"GCN_KAFKA_CLIENT_SECRET: {os.getenv('GCN_KAFKA_CLIENT_SECRET')}")

    client_id = environ.get("GCN_KAFKA_CLIENT_ID")
    client_secret = environ.get("GCN_KAFKA_CLIENT_SECRET")

    if not client_id or not client_secret:
        logger.error("GCN_KAFKA_CLIENT_ID and GCN_KAFKA_CLIENT_SECRET must be set in the environment.")
        sys.exit(1)

    slack_token = environ.get("SLACK_TOKEN_CR")
    send_to_slack = bool(slack_token)

    if slack_token:
        slack_client = WebClient(token=slack_token)
        logger.debug("Created Slack client")
    else:
        slack_client = None

    consumer = Consumer(client_id=client_id,
                        client_secret=client_secret,
                        config = {'auto.offset.reset': 'earliest'})
    consumer.subscribe(['gcn.notices.einstein_probe.wxt.alert',
                        'gcn.classic.voevent.FERMI_GBM_GND_POS',
                        'gcn.classic.voevent.MAXI_KNOWN',
                        'gcn.notices.chime.frb',
                        'gcn.classic.voevent.SWIFT_BAT_GRB_POS_ACK'])

    while True:
        for message in consumer.consume(timeout=5):
        if message.error():
            logger.error(message.error())
            continue

        try:
            #logger.debug(f'Received message: {message.value().decode("utf-8")}')
            topic = message.topic()
            offset = message.offset()
            print(f'Topic: {topic}. Offset: {offset}')
            alert, alert_format = parse_alert_payload(message.value())
            rate_duration = alert.get("rate_duration", None)
            event_time_str = alert.get("trigger_time", None)
            logger.debug(
                f'Received {alert_format} alert: mission={alert.get("mission", "Unknown")}, '
                f'instrument={alert.get("instrument", "Unknown")}, trigger_time={event_time_str}'
            )

            event_time = parse_event_time(event_time_str)
            current_time = datetime.utcnow(), slack_client
            print('current time', current_time, 'event time', event_time)

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
                    f"GCN alert: Instrument: {alert.get('instrument', 'Unknown')}. Mission: {alert.get('mission', 'Unknown')}.\n"
                    f"RA, Dec = ({alert['ra']}, {alert['dec']}, radius={alert['radius']}).\n"
                    f"Rate_duration: {rate_duration}. Rate_snr: {alert.get('rate_snr', 'N/A')}."
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
                    f"GCN alert: Instrument: {alert.get('instrument', 'Unknown')}.\n"
                    f"RA, Dec = ({alert['ra']}, {alert['dec']}, ra_dec_error={alert['ra_dec_error']}).\n"
                    f"Net count rate: {alert['net_count_rate']}. Image SNR: {alert['image_snr']}."
                )
                if send_to_slack:
                    post_to_slack(slack_channel, message, slack_client)
            else:
                logger.info(f"Alert did not match known criteria; format={alert_format}; keys={list(alert.keys())}")

            except Exception as e:
                logger.error(f'Error processing message: {e}')

