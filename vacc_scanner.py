import time
import requests
import smtplib
import random

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# CoWin Config
"""
Find district Id from https://getjab.in/ district (sorted by alphabet - showing district id in front)
"""
DISTRICT_ID = "725"  # Kolkata
DATE_LIST = ["10-05-2021", "11-05-2021"]     # Double digit format DD-MM-YYYY
MIN_AGE_LIMIT = 18
COWIN_API = "https://cdn-api.co-vin.in/api/v2/appointment/sessions/calendarByDistrict?district_id=" + DISTRICT_ID + "&date="

SCAN_TIME_INTERVAL_MIN = 60  # 60 seconds
SCAN_TIME_INTERVAL_MAX = 90  # 90 seconds

# Notification config
"""
******** DO NOT USE PERSONNEL GMAIL ID ********

1. create dummy gmail id
2. Allow IMAP from gmail settings
2. Allow "less secure app" in gmail settings
4. following GMAIL_USER/PASSWORD config used by the app to sign in to gmail to send mail
5. MAIL_TO_GMAIL_ID is the list of mail ids to which mail will be sent (can be single and same as sign in)
"""
MAIL_NOTIFICATION_ALLOWED = True
GMAIL_USER = 'abc.pqr@gmail.com'
GMAIL_PASSWORD = 'abcd1234'
MAIL_TO_GMAIL_IDS = ['abc.pqr@gmail.com', 'xxx.yyy@gmail.com']
APPEND_UTC_TIME_IN_SUBJECT = True   # This will generate new subject in mail if True


class CowinScanner():

    @classmethod
    def make_request(cls, date):
        data = None

        # EXTREMELY IMPORTANT - FAKE THE REQUEST AS IF FROM BROWSER CHROME
        my_headers = {'Host': 'cdn-api.co-vin.in',
                      'Connection': 'keep-alive',
                      'Cache-Control': 'max-age=0',
                      'sec-ch-ua': '" Not A;Brand";v="99", "Chromium";v="90", "Google Chrome";v="90"',
                      'sec-ch-ua-mobile': '?0',
                      'DNT': '1',
                      'Upgrade-Insecure-Requests': '1',
                      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36',
                      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
                      'Sec-Fetch-Site': 'none',
                      'Sec-Fetch-Mode': 'navigate',
                      'Sec-Fetch-User': '?1',
                      'Sec-Fetch-Dest': 'document',
                      'Accept-Encoding': 'gzip, deflate, br',
                      'Accept-Language': 'en-US,en-IN;q=0.9,en;q=0.8'}

        try:
            url = COWIN_API + date
            print("===== hit API: ", url)
            response = requests.get(url, headers=my_headers, verify=False)
            status_code = response.status_code
            if status_code == 200:
                data = response.json()
            else:
                print("ERROR: Cowin API status_code: ", status_code)
        except requests.exceptions.HTTPError as errh:
            print("Cowin API HTTPError: ", errh)
        except requests.exceptions.ConnectionError as errc:
            print("Cowin API ConnectionError: ", errc)
        except requests.exceptions.Timeout as errt:
            print("Cowin API TimeoutError: ", errt)
        except requests.exceptions.RequestException as err:
            print("Cowin API RequestException: ", err)
        return data

    @classmethod
    def parse_data(cls, data):
        notify_dict = {}

        if data and 'centers' in data:
            centers_list = data['centers']
            for center in centers_list:
                center_name = center.get('name', None)
                slot_available = 0
                if 'sessions' in center:
                    sessions_list = center['sessions']
                    for session in sessions_list:
                        availability = session.get('available_capacity')
                        age_limit = session.get('min_age_limit')
                        if availability > 0 and age_limit >= MIN_AGE_LIMIT:
                            slot_available = slot_available + availability
                            notify_dict[center_name] = {'slots': slot_available, 'age': age_limit}
        return notify_dict

    @classmethod
    def format_notif_msg(cls, notify_dict):
        notif_str = ""
        for key in notify_dict.keys():
            center_name = key
            # center_name = center_name[0:6]  # strip chars for SMS
            available = notify_dict[key].get('slots')
            age_limit = notify_dict[key].get('age')
            notif_str = notif_str + center_name + ": slots-" + str(available) + ", min age-" + str(age_limit) + ". " + "\n"
        return notif_str

    @classmethod
    def send_notification_mail(cls, notify_dict, date):
        body = cls.format_notif_msg(notify_dict)

        # Setup the MIME
        message = MIMEMultipart()
        message['From'] = GMAIL_USER
        message['To'] = MAIL_TO_GMAIL_IDS[0]
        time_now = "[" + str(round(time.time())) + "]" if APPEND_UTC_TIME_IN_SUBJECT else ""
        message['Subject'] = "[CoWin Vaccine][" + date + "]: slot availability " + time_now  # The subject line

        mail_content = body
        message.attach(MIMEText(mail_content, 'plain'))

        try:
            session = smtplib.SMTP('smtp.gmail.com', 587)  # use gmail with port
            session.starttls()  # enable security
            session.login(GMAIL_USER, GMAIL_PASSWORD)  # login with mail_id and password
            text = message.as_string()
            session.sendmail(GMAIL_USER, MAIL_TO_GMAIL_IDS, text)
            session.quit()
            print("Email notification Sent to: ", MAIL_TO_GMAIL_IDS, ", body: ", mail_content)
        except Exception as err:
            print(err)

    @classmethod
    def post_msg(cls, notify_dict):
        message = cls.format_notif_msg(notify_dict)
        try:
            my_headers = {'Authorization': 'Bearer {access_token}'}
            my_data = {'data': message}
            response = requests.post('http://httpbin.org/headers', headers=my_headers, data=my_data)
        except requests.exceptions.HTTPError as errh:
            print(errh)
        except requests.exceptions.ConnectionError as errc:
            print(errc)
        except requests.exceptions.Timeout as errt:
            print(errt)
        except requests.exceptions.RequestException as err:
            print(err)

    @classmethod
    def process_date(cls, date):
        # Request API
        data = cls.make_request(date)

        # Parse data
        notify_dict = cls.parse_data(data)

        # Send notification
        if len(notify_dict.keys()) > 0 and MAIL_NOTIFICATION_ALLOWED:
            cls.send_notification_mail(notify_dict, date)

    @classmethod
    def scan(cls):
        # Infinite loop - careful - cdn may block if timer not proper
        while True:
            for date_search in DATE_LIST:
                cls.process_date(date_search)

                # IMPORTANT: sleep for random time secs, ditch pattern crawler
                delay = random.randint(SCAN_TIME_INTERVAL_MIN, SCAN_TIME_INTERVAL_MAX)
                time.sleep(delay)


"""
Main function
"""
if __name__ == '__main__':
    CowinScanner.scan()
