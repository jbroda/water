import smtplib
import base64
import struct
import json
import time
import os
import pickle
import logging.config
import requests
from lxml import html, etree
from datetime import date, datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

###############################################################################
from typing import Optional, Any

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGGER_CONF = os.path.join(BASE_DIR, 'logging.conf')
METER_IDS = os.path.join(BASE_DIR, 'meter_ids.p')

logging.config.fileConfig(LOGGER_CONF)
logger = logging.getLogger('water')

retry = Retry(total=None, connect=10, read=10, redirect=10, status=10, backoff_factor=0.5)
adapter = HTTPAdapter(max_retries=retry)
session = requests.Session()
session.mount('http://', adapter)
session.mount('https://', adapter)

###############################################################################
WATER_FILE = 'WaterRecords.html'
JSON_FILE  = 'data.json'

WATER_METER_URL1 = "https://vospub.ci.schaumburg.il.us/WaterUsage/Home/Index?AccountNum="
WATER_METER_URL2 = "https://199.20.14.37/WaterUsage/Home/Index?AccountNum="

WATER_USAGE_URL1 = "https://vospub.ci.schaumburg.il.us/WaterUsage/Home/AjaxMethod?MeterID="
WATER_USAGE_URL2 = "https://199.20.14.37/WaterUsage/Home/AjaxMethod?MeterID="

MAX_DAILY_USAGE = 2000  # max usage in gallons per day
MAX_ELAPSED_DAYS_SINCE_READING = 4
MAX_CONNECT_TRIES = 6

# DEBUG = True
DEBUG = False

# OPEN_FILE = True
OPEN_FILE = False

SEND_EMAIL = True
# SEND_EMAIL = False

# LOAD_CACHED_METER_IDS = True
LOAD_CACHED_METER_IDS = False

ACCOUNTS = [
    ('202379-52506', '905 Casey Ct'),
    ('202379-52507', '909 Casey Ct'),
    ('202379-52508', '913 Casey Ct'),
    ('202379-52509', '921 Casey Ct'),
    ('202379-52510', '925 Casey Ct'),
    ('202379-52511', '929 Casey Ct'),
    ('202379-52512', '931 Casey Ct'),
    ('202379-52513', '928 Casey Ct'),
    ('202379-52514', '924 Casey Ct'),
    ('202379-52515', '920 Casey Ct'),
    ('202379-52516', '916 Casey Ct'),
    ('202379-52517', '908 Casey Ct'),
    ('202379-52518', '904 Casey Ct'),
    ('202379-52519', '900 Casey Ct'),
    ('202379-52520', '901 Buccaneer Dr'),
    ('202379-52521', '905 Buccaneer Dr'),
    ('202379-52522', '909 Buccaneer Dr'),
    ('202379-52523', '917 Buccaneer Dr'),
    ('202379-52524', '921 Buccaneer Dr'),
    ('202379-52525', '925 Buccaneer Dr'),
    ('202379-52526', '929 Buccaneer Dr'),
    ('202379-52527', '2640 Pirates Cove'),
    ('202379-52528', '2636 Pirates Cove'),
    ('202379-52529', '2632 Pirates Cove'),
    ('202379-52530', '2624 Pirates Cove'),
    ('202379-52531', '2620 Pirates Cove'),
    ('202379-52532', '2612 Pirates Cove'),
    ('202379-52533', '2608 Pirates Cove'),
    ('202379-52534', '2600 Pirates Cove'),
    ('202379-52535', '2609 Pirates Cove'),
    ('202379-52536', '2613 Pirates Cove'),
    ('202379-52537', '2625 Pirates Cove'),
    ('202379-52538', '2629 Pirates Cove'),
    ('202379-52539', '1001 Buccaneer Dr'),
    ('202379-52540', '1005 Buccaneer Dr'),
    ('202379-52541', '1009 Buccaneer Dr'),
    ('202379-52542', '1017 Buccaneer Dr'),
    ('202379-52543', '1021 Buccaneer Dr'),
    ('202379-52544', '1029 Buccaneer Dr'),
    ('202379-52545', '1033 Buccaneer Dr'),
    ('202379-52546', '1037 Buccaneer Dr')
]

if OPEN_FILE:
    ACCOUNTS = [
        ('202379-52506', '905 Casey Ct'),
        ('202379-52512', '931 Casey Ct'),
        ('202379-52522', '909 Buccaneer Dr'),
    ]

FROM          = 'Water Usage <admin@XXXXXXXXX.XX>'
TO_LEAK_FOUND = 'Hidden Pond <contact@XXXXXXXXX.XX>'
TO_NO_LEAK    = 'HP Admin <admin@XXXXXXXXX.XX>'
# TO_LEAK_FOUND = TO_NO_LEAK

LOGIN = 'admin@XXXXXXXXX.XX'
PASSWD = 'XXXXXXXXXXX'
SERVER = 'smtp.XXXXX.com'

PORT = 587


##############################################################################
def unichar(i):
    try:
        return unichr(i)
    except ValueError:
        return struct.pack('i', i).decode('utf-32')


##############################################################################
def goomoji_decode(code):
    # Base64 decode.
    binary = base64.b64decode(code)
    # UTF-8 decode.
    decoded = binary.decode('utf8')
    # Get the UTF-8 value.
    value = ord(decoded)
    # Hex encode, trim the 'FE' prefix, and uppercase.
    return format(value, 'x')[2:].upper()


##############################################################################
def goomoji_encode(code):
    # Add the 'FE' prefix and decode.
    value = int('FE' + code, 16)
    # Convert to UTF-8 character.
    encoded = unichar(value)
    # Encode UTF-8 to binary.
    binary = bytearray(encoded, 'utf8')
    # Base64 encode return end return a UTF-8 string.
    return base64.b64encode(binary).decode('utf-8')


##############################################################################
def send_email(text_message_list, html_message_list):
    try:
        new_text_msg = ""
        new_html_msg = ""

        leak_found = len(text_message_list) > 0

        if leak_found:
            new_html_msg = "<ul>"

            for msg in text_message_list:
                new_text_msg = new_text_msg + msg + "\n"

            for msg in html_message_list:
                new_html_msg = new_html_msg + msg + "\n"
        else:
            new_text_msg = "No leaks found."
            new_html_msg = "<i>No leaks found.</i>"

        if leak_found:
            new_html_msg = new_html_msg + "</ul>"

        ### goomoji = '=?UTF-8?B?{0}?='.format(goomoji_encode('7f9')) # Alarm light.
        siren_emoji = u"\U0001F6A8"
        water_emoji = u"\U0001F4A6"

        if leak_found:
            emoji_left  = water_emoji + siren_emoji + water_emoji
            emoji_right = water_emoji + siren_emoji + water_emoji
            subject = (emoji_left + 'Water Leak!' + emoji_right)
        else:
            emoji_left  = water_emoji
            emoji_right = water_emoji
            subject = (emoji_left + 'No Water Leak!' + emoji_right)

        TO = TO_LEAK_FOUND if leak_found else TO_NO_LEAK

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = FROM
        msg['To'] = TO
        msg['Reply-To'] = FROM
        msg['Bcc'] = TO_NO_LEAK

        part1 = MIMEText(new_text_msg, 'plain')
        part2 = MIMEText(new_html_msg, 'html')

        msg.attach(part1)
        msg.attach(part2)

        logger.info('Connecting to {0}:{1} ...'.format(SERVER, PORT))
        s = smtplib.SMTP(SERVER, PORT)
        # s.set_debuglevel(1)
        s.ehlo()
        s.starttls()
        logger.info('Logging in ...')
        s.login(LOGIN, PASSWD)
        logger.info('Sending email ...')
        s.sendmail(FROM, [TO], msg.as_string())
        logger.info('Sent email!')
        s.quit()
    except Exception as e:
        logger.error('Exception: ' + str(e))


##############################################################################
def send_error_email(err_message_list):
    try:
        err_text_msg = ""
        err_html_msg = "<ul>"

        for msg in err_message_list:
            err_text_msg = err_text_msg + msg + "\n"
            err_html_msg = err_html_msg + "<li>" + msg + "</li>" + "\n"

        err_html_msg = err_html_msg + "</ul>"

        msg = MIMEMultipart('alternative')

        TO = TO_NO_LEAK

        msg['Subject'] = 'Water Leak script ERROR!'
        msg['From'] = FROM
        msg['To'] = TO
        msg['Reply-To'] = FROM
        msg['Bcc'] = TO_NO_LEAK

        part1 = MIMEText(err_text_msg, 'plain')
        part2 = MIMEText(err_html_msg, 'html')

        msg.attach(part1)
        msg.attach(part2)

        logger.info('Connecting to {0}:{1} ...'.format(SERVER, PORT))
        s = smtplib.SMTP(SERVER, PORT)
        # s.set_debuglevel(1)
        s.ehlo()
        s.starttls()
        logger.info('Logging in ...')
        s.login(LOGIN, PASSWD)
        logger.info('Sending email ...')
        s.sendmail(FROM, [TO], msg.as_string())
        logger.info('Sent email!')
        s.quit()
    except Exception as e:
        logger.error('Exception: ' + str(e))


##############################################################################
def get_water_meter_id(stream, account, addr, err_message_list):
    meter_id = None
    try:
        if DEBUG:
            logger.info('Getting Water Meter ID for {0} at {1} ...'.format(account, addr))

        tree = html.fromstring(stream)
        meter_id = tree.xpath('//div[@id="Meter"]')[0].text_content().strip()

        if DEBUG:
            logger.info('Water Meter ID for {0} at {1} is {2}'.format(account, addr, meter_id))

    except Exception as e:
        err = "get_water_meter_id: EXCEPTION(acct {0} at {1}): {2}".format(account, addr, str(e))
        err_message_list.append(err)
        # send_error_email(err)
        logger.error(err)

    return meter_id


##############################################################################
def check_water_usage(stream, addr, url, text_message_list, html_message_list, err_message_list):
    try:
        data = json.loads(stream)

        # Remove the header row from 'tableDataHigh.
        row = data['tableDataHigh'][1:]

        gallons = [float(row[0][2]) * 1000.0, 
                   float(row[1][2]) * 1000.0]

        dates = [datetime.strptime(row[0][1], "%m/%d/%Y"), 
                 datetime.strptime(row[1][1], "%m/%d/%Y")]

        since_last_reading = datetime.today() - dates[0]

        if since_last_reading.days >= MAX_ELAPSED_DAYS_SINCE_READING:
            logger.debug("today: {0}, last reading: {1}".format(datetime.today(), dates[0]))
            raise Exception("Elapsed {0} days since last reading!".format(since_last_reading.days))

        usage = gallons[0] - gallons[1]
        period = dates[0] - dates[1]
        secs_per_day = 24*60*60    # hours * minutes * secs
        days = period.total_seconds() / secs_per_day
        daily_usage = usage / days
        if DEBUG:
            logger.info("  PERIOD: {0:.2f} days".format(days))
            logger.info("  USAGE:  {0:.2f} gal".format(usage))
            logger.info("  DAILY USAGE: {0:.2f} gal/day".format(daily_usage))
        dt = dates[0]
        if daily_usage >= MAX_DAILY_USAGE:
            logger.info("  found a leak of {0:.2f} gal/day at {1}".format(daily_usage, addr))
            text_message_list.append("* LEAK: {0:.2f} gal/day at {1} on {2:%A, %B %d, %Y} at {3:%I:%M:%S %p}!\n  Check at {4}\n".\
                                     format(daily_usage, addr, dt.date(), dt.time(), url))
            html_message_list.append("<li style='margin: 20px 0;'> <b>LEAK</b>: {0:.2f} gal/day at {1} on {2:%A, %B %d, %Y} at {3:%I:%M:%S %p}!<br />Check at {4}<br />".\
                                     format(daily_usage, addr, dt.date(), dt.time(), url))
        else:
            logger.info("  usage: {0:.2f} gal/day at {1}".format(daily_usage, addr))
    except Exception as e:
        err = "check_water_usage: EXCEPTION({0}, {1}): {2}".format(addr, url, str(e))
        # send_error_email(err)
        err_message_list.append(err)
        logger.error(err)


##############################################################################
def connect(url, url_type):  #, account_num, account_addr, err_message_list):
    text = None

    try:
        if DEBUG:
            logger.debug("Connecting to {0} URL: {1} ...".format(url_type, url))
        response = session.get(url)
        text = response.text
        if DEBUG and text:
            logger.debug("Connected to {0} URL: {1}!".format(url_type, url))
        
    except Exception as e:
        logger.exception(e)

    return text


##############################################################################
def save(filename, *objects):
    # save objects into a compressed disk file
    fil = open(filename, 'wb')
    for obj in objects:
        pickle.dump(obj, fil)
    fil.close()


##############################################################################
def load(filename):
    # reload objects from a compressed disk file
    fil = open(filename, 'rb')
    r = pickle.load(fil)
    fil.close()
    return r


##############################################################################
def main():
    logger.info("Checking water usage ...")

    try:
        text_message_list = []
        html_message_list = []
        err_message_list = []

        account_num = ""
        account_addr = ""
        account_url = ""

        water_meter_ids = {}

        try:
            if LOAD_CACHED_METER_IDS:
                water_meter_ids = load(METER_IDS)
        except Exception as e:
            # logger.exception(e)
            pass

        for account in ACCOUNTS:
            account_num = account[0]
            account_addr = account[1]

            water_meter_id = None

            try:
                water_meter_id = water_meter_ids[account_num]
            except Exception as e:
                # logger.exception(e)
                pass

            meter_id_url = WATER_METER_URL1 + account_num

            #
            # Read the water meter URL and get the Water Meter ID.
            #
            if not water_meter_id:
                account_url = meter_id_url

                if OPEN_FILE:
                    if DEBUG:
                        logger.info("Opening file '{0}' ...".format(WATER_FILE))
                    f = open(WATER_FILE)
                    stream = f.read()
                else:
                    text = connect(meter_id_url, "meter")

                    if not text:
                        err = "Connect FAILED for account: {0}, addr: {1}, url: {2} after {3} tries!".\
                              format(account_num, account_addr, meter_id_url, 5)
                        logger.error(err)
                        err_message_list.append(err)
                        continue

                    stream = text

                water_meter_id = get_water_meter_id(stream, account_num, account_addr, err_message_list)

                water_meter_ids[account_num] = water_meter_id

            if not water_meter_id:
                err = "Water Meter ID is empty for {0} at {1}!".format(account_num, account_addr)
                # send_error_email(err)
                err_message_list.append(err)
                logger.error(err)
                continue

            logger.info("- account: {0}, addr: {1}, meter ID: {2} ...".format(account_num, account_addr, water_meter_id))

            #
            # Read the water usage URL and get the usage.
            #
            water_usage_url = WATER_USAGE_URL1 + water_meter_id
            account_url = water_usage_url

            if OPEN_FILE:
                if DEBUG:
                    logger.info("Opening JSON file '{0}'...".format(JSON_FILE))
                f = open(JSON_FILE)
                stream = f.read()
            else:
                text = connect(water_usage_url, "usage")

                if not text:
                    err = "Connect FAILED for account: {0}, addr: {1}, url: {2} after {3} tries!". \
                          format(account_num, account_addr, water_usage_url, 5)
                    logger.error(err)
                    err_message_list.append(err)
                    continue

                stream = text 

            check_water_usage(stream, account_addr, meter_id_url,
                              text_message_list, html_message_list,
                              err_message_list)

        save(METER_IDS, water_meter_ids)

        if not SEND_EMAIL:
            logger.info("TXT:  " + str(text_message_list))
            logger.info("HTML: " + str(html_message_list))

            for idx, err in enumerate(err_message_list):
                logger.info("ERR[{0}]: {1}".format(idx, str(err)))
        else:
            send_email(text_message_list, html_message_list)

            if len(err_message_list) > 0:
                send_error_email(err_message_list)

    except Exception as e:
        err = "EXCEPTION(acct {0} at {1}): {2}, URL: {3}".format(account_num, account_addr, html.escape(str(e)), account_url)
        err_message_list = [err]
        send_error_email(err_message_list)
        logger.error(err)

    logger.info("Done!")


##############################################################################
if __name__ == "__main__":
    """
    text_message_list = ["test"]
    html_message_list = ["test"]
    send_email(text_message_list, html_message_list)
    """
    start_dt = datetime.now()
    main()
    end_dt = datetime.now()
    elapsed = end_dt - start_dt
    logger.info("running time: {0} sec".format(elapsed.seconds))
