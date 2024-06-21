import os
import time
import hashlib
import requests
import threading
from flask import Flask, jsonify
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, NoSuchDriverException
from selenium.webdriver.chrome.service import Service as ChromeService

# Constants
EXTENSION_ID = 'lkbnfiajjmbhnfledhphioinpickokdi'
CRX_URL = "https://clients2.google.com/service/update2/crx?response=redirect&prodversion=98.0.4758.102&acceptformat=crx2,crx3&x=id%3D~~~~%26uc&nacl_arch=x86-64"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36"
IMGUR_CLIENT_ID = os.getenv('IMGUR_CLIENT_ID', '')

# Environment variables
USER = os.getenv('GRASS_USER', '')
PASSW = os.getenv('GRASS_PASS', '')
ALLOW_DEBUG = os.getenv('ALLOW_DEBUG', 'False').lower() == 'true'

# Check if necessary environment variables are set
def check_env_variables():
    if not USER or not PASSW:
        print('Please set GRASS_USER and GRASS_PASS env variables')
        exit()

    if ALLOW_DEBUG:
        print('Debugging is enabled! This will generate a screenshot and console logs on error!')
        if not IMGUR_CLIENT_ID:
            raise EnvironmentError(
                'Please set IMGUR_CLIENT_ID env variables')

# Function to generate error report
def generate_error_report(driver):
    if not ALLOW_DEBUG:
        return

    try:
        # Take a screenshot
        screenshot_path = 'error.png'
        driver.save_screenshot(screenshot_path)

        # Get console logs
        logs = driver.get_log('browser')
        log_path = 'error.log'
        with open(log_path, 'w') as f:
            for log in logs:
                f.write(str(log))
                f.write('\n')

        # Upload the screenshot to Imgur
        url = 'https://api.imgur.com/3/upload'
        headers = {'Authorization': f'Client-ID {IMGUR_CLIENT_ID}'}
        with open(screenshot_path, 'rb') as image_file:
            files = {'image': image_file}
            response = requests.post(url, headers=headers, files=files)

        if response.status_code == 200:
            data = response.json()
            image_url = data['data']['link']
            print('Screenshot uploaded successfully.')
            print('Image URL:', image_url)
        else:
            print(f'Failed to upload screenshot. Status code: {response.status_code}')
            print('Response:', response.text)

        print('Error report generated! Provide the above information to the developer for debugging purposes.')

    except Exception as e:
        print(f'An error occurred while generating the error report: {str(e)}')

# Function to download extension
def download_extension(extension_id):
    url = CRX_URL.replace("~~~~", extension_id)
    headers = {"User-Agent": USER_AGENT}
    response = requests.get(url, stream=True, headers=headers)
    with open("grass.crx", "wb") as fd:
        for chunk in response.iter_content(chunk_size=128):
            fd.write(chunk)
    if ALLOW_DEBUG:
        md5 = hashlib.md5(open('grass.crx', 'rb').read()).hexdigest()
        print(f'Extension MD5: {md5}')

def reconnect_extension(driver):
        try:
            webdriver(driver, 5).until(
                EC.presence_of_element_located(
                    (By.XPATH, '//p[contains(text(), "Reconnect"]'))
            )
            print('Found the "Reconnect" link!')
            driver.find_element(By.XPATH, '//p[contains(text(), "Reconnect"]').click()
        except Exception as e:
            # No need to reconnect extension, continue
            return

# Function to refresh the page periodically
def refresh_task(driver):
    print("Refresh task started....")
    try:
        while True:
            data = get_data(driver)
            print(data)
            driver.refresh()
            time.sleep(60)
    except KeyboardInterrupt:
        print("Selenium task stopped by user")
    finally:
        driver.quit()

# Function to retrieve data from the dashboard
def get_data(driver):
    try:
        network_quality = driver.find_element('xpath', '//*[contains(text(), "Network Quality:")]').find_element('xpath', 'following-sibling::p').text
    except:
        network_quality = False
        generate_error_report(driver)
        print('Could not get network quality!')

    try:
        token = driver.find_element('xpath', '//*[@alt="token"]').find_element('xpath', 'following-sibling::div').text
        epoch_earnings = token
    except:
        epoch_earnings = False
        generate_error_report(driver)
        print('Could not get earnings!')

    try:
        driver.find_element('xpath', '//*[contains(text(), "Grass is Connected")]')
        connected = True
    except:
        connected = False
        generate_error_report(driver)
        print('Could not get connection status!')

    return {'connected': connected, 'network_quality': network_quality, 'epoch_earnings': epoch_earnings}

# Function to initialize and configure the WebDriver
def initialize_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument('--no-sandbox')
    options.add_extension('grass.crx')

    print('Installed! Starting...')
    try:
        driver = webdriver.Chrome(options=options)
    except (WebDriverException, NoSuchDriverException):
        print('Could not start with Manager! Trying to default to manual path...')
        try:
            service = ChromeService(executable_path="/usr/bin/chromedriver")
            driver = webdriver.Chrome(service=service, options=options)
        except (WebDriverException, NoSuchDriverException):
            print('Could not start with manual path! Exiting...')
            exit()
    return driver

# Function to login to the dashboard
def login(driver):
    print('Started! Logging in...')
    driver.get('https://app.getgrass.io/')
    sleep = 0
    while True:
        try:
            driver.find_element('xpath', '//*[@name="user"]')
            driver.find_element('xpath', '//*[@name="password"]')
            driver.find_element('xpath', '//*[@type="submit"]')
            break
        except:
            time.sleep(1)
            print('Loading login form...')
            sleep += 1
            if sleep > 15:
                print('Could not load login form! Exiting...')
                generate_error_report(driver)
                driver.quit()
                exit()

    # Fill in username and password
    driver.find_element('xpath', '//*[@name="user"]').send_keys(USER)
    driver.find_element('xpath', '//*[@name="password"]').send_keys(PASSW)
    driver.find_element('xpath', '//*[@type="submit"]').click()

    sleep = 0
    while True:
        try:
            driver.find_element('xpath', '//*[contains(text(), "Dashboard")]')
            break
        except:
            time.sleep(1)
            print('Logging in...')
            sleep += 1
            if sleep > 30:
                print('Could not login! Double-check your username and password! Exiting...')
                generate_error_report(driver)
                driver.quit()
                exit()

# Function to wait for the connection
def wait_for_connection(driver):
    print('Logged in! Waiting for connection...')
    driver.get(f'chrome-extension://{EXTENSION_ID}/index.html')
    sleep = 0
    while True:
        try:
            driver.find_element('xpath', '//*[contains(text(), "Grass is Connected")]')
            break
        except:
            time.sleep(1)
            print('Loading connection...')
            sleep += 1
            if sleep > 30:
                print('Could not load connection! Exiting...')
                generate_error_report(driver)
                driver.quit()
                exit()

# Function to set up and run the Flask API
def start_flask_api(driver):
    app = Flask(__name__)

    @app.route('/')
    def get():
        try:
            data = get_data(driver)
            for key in data:
                if data[key] is None:
                    data[key] = False
            return jsonify(data)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    selenium_thread = threading.Thread(target=refresh_task, args=(driver,))
    selenium_thread.start()
    app.run(host='0.0.0.0', port=80, debug=False)

# Main function
def main():
    check_env_variables()
    # Uncomment if the extension needs to be downloaded
    # download_extension(EXTENSION_ID)
    driver = initialize_driver()
    login(driver)
    wait_for_connection(driver)
    print('Connected! Starting API...')
    start_flask_api(driver)
    driver.quit()

if __name__ == '__main__':
    main()
