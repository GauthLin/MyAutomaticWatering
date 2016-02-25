#!/usr/bin/python
# -*- coding: utf-8 -*-

##################################
#  Automatic Watering            #
#                                #
#  Flowers are now always happy  #
#                                #
#  Linard Gauthier               #
##################################

import param
import time
import datetime
import RPi.GPIO as GPIO
import math
import multiprocessing


class Watering:
    def __init__(self):
        # Watering
        self.daysBetweenWatering = 4  # Number of days between one watering
        self.startTime = [23, 00]  # [hh, mm]
        self.durationOfWatering = 60  # in minutes
        self.modeList = ['AUTO', 'OFF', 'ON']  # List of available modes
        self.currentModeSelected = 0
        self.lastWatering = None  # Last date of watering
        self.ongoingWatering = False  # Is the watering on going or not
        self.endWateringDate = None  # Contains the datetime of the end of the current watering

        # Emergency
        self.emergency_on = False

        # Process
        self.watering_process = None
        self.emergency_process = None

        # Menu
        self.currentMenuSelected = 0
        self.configMenuSelected = 0

        self.HOME_MENU = 0
        self.CONFIG_MENU = 1
        self.EMERGENCY_MENU = 3
        self.mainMenu = {
            0: self.display_menu_home,
            1: self.display_config_menu,
            2: self.display_config_details,
            3: self.display_emergency
        }

        self.START_STOP_WATERING_CONFIG_MENU = 0
        self.DAYS_OF_WATERING_CONFIG_MENU = 1
        self.START_WATERING_AT_CONFIG_MENU = 2
        self.DURATION_OF_WATERING_CONFIG_MENU = 3
        self.MODE_SELECTION_CONFIG_MENU = 4
        self.configMenu = {
            0: (self.mainMenu[self.HOME_MENU], "Démarrer/Arrêter"),
            1: (self.display_menu_watering_days, "Jours d'arro."),
            2: (self.display_menu_start_time, "Heure d'arro."),
            3: (self.display_menu_duration, "Durée d'arro."),
            4: (self.display_menu_mode, "Mode d'arro.")
        }

        # Setup the GPIOs
        self.setup_gpio(param.GPIO)

        # Test if all LEDs work
        GPIO.output(param.GPIO['led']['green'][1], GPIO.HIGH)
        GPIO.output(param.GPIO['led']['red'][1], GPIO.HIGH)
        time.sleep(2)
        GPIO.output(param.GPIO['led']['green'][1], GPIO.LOW)
        GPIO.output(param.GPIO['led']['red'][1], GPIO.LOW)

        self.start()

    def start(self):
        while True:
            # Displays the menu
            self.display_menu()

            # Calculates if it has to water or not
            # If mode ON -> start watering
            if self.modeList[self.currentModeSelected] == "ON" and not self.ongoingWatering:
                self.start_watering()
            # If mode OFF stop watering
            elif self.modeList[self.currentModeSelected] == "OFF" and self.ongoingWatering:
                self.stop_watering()
            # If mode AUTO
            elif self.has_to_water() and not self.ongoingWatering:
                self.start_watering()
            # Stops the watering after duration specified
            elif self.ongoingWatering and self.endWateringDate < datetime.datetime.today():
                self.stop_watering()
            time.sleep(1)

    # GPIO configuration
    def setup_gpio(self, array):
        GPIO.setmode(GPIO.BCM)

        # v[0] contains the key
        # v[1] contains the value
        for v in array.items():
            if isinstance(v[1], dict):
                self.setup_gpio(v[1])
            else:
                if v[1][0].upper() == "IN":
                    GPIO.setup(v[1][1], GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

                    # Define callback method
                    if v[0] in ['left', 'right']:
                        GPIO.add_event_detect(v[1][1], GPIO.FALLING, callback=self.left_right_btn_pressed, bouncetime=500)
                    elif v[0] in ['up', 'bottom']:
                        GPIO.add_event_detect(v[1][1], GPIO.FALLING, callback=self.up_bottom_btn_pressed, bouncetime=500)
                    elif v[0] == 'emergency':
                        GPIO.add_event_detect(v[1][1], GPIO.FALLING, callback=self.emergency_btn_pressed, bouncetime=2000)
                else:
                    GPIO.setup(v[1][1], GPIO.OUT)

    # Changes the currentMenuSelected
    def left_right_btn_pressed(self, channel):
        if self.emergency_on:
            return

        if param.GPIO['btn']['right'][1] == channel:
            if self.emergency_on:
                return

            self.currentMenuSelected = self.currentMenuSelected + 1 if self.currentMenuSelected < len(self.mainMenu) - 2 else 0
        elif param.GPIO['btn']['left'][1] == channel:
            if self.emergency_on:
                return

            self.currentMenuSelected = self.currentMenuSelected - 1 if self.currentMenuSelected > 0 else 0

    # Changes the value of the corresponding currentMenuSelected
    def up_bottom_btn_pressed(self, channel):
        # Change the current selected config menu
        if self.currentMenuSelected == self.CONFIG_MENU:
            if param.GPIO['btn']['up'][1] == channel:
                self.configMenuSelected = self.configMenuSelected - 1 if self.configMenuSelected > 0 else len(self.configMenu) - 1
            if param.GPIO['btn']['bottom'][1] == channel:
                self.configMenuSelected = self.configMenuSelected + 1 if self.configMenuSelected < len(self.configMenu) - 1 else 0

        # Adds or removes days between watering
        elif self.configMenuSelected == self.DAYS_OF_WATERING_CONFIG_MENU:
            if param.GPIO['btn']['up'][1] == channel:
                self.daysBetweenWatering = self.daysBetweenWatering + 1 if self.daysBetweenWatering < 7 else 1
            if param.GPIO['btn']['bottom'][1] == channel:
                self.daysBetweenWatering = self.daysBetweenWatering - 1 if self.daysBetweenWatering > 1 else 7

        # Defines the time when the watering must start
        elif self.configMenuSelected == self.START_WATERING_AT_CONFIG_MENU:
            if param.GPIO['btn']['up'][1] == channel:
                self.add_start_time()
            if param.GPIO['btn']['bottom'][1] == channel:
                self.remove_start_time()

        # Adds or removes the duration of watering
        elif self.configMenuSelected == self.DURATION_OF_WATERING_CONFIG_MENU:
            if param.GPIO['btn']['up'][1] == channel:
                self.durationOfWatering += 10
            if param.GPIO['btn']['bottom'][1] == channel:
                self.durationOfWatering -= 10

        # Changes the current mode
        elif self.configMenuSelected == self.MODE_SELECTION_CONFIG_MENU:
            if param.GPIO['btn']['up'][1] == channel:
                self.currentModeSelected = self.currentModeSelected + 1 if self.currentModeSelected < 2 else 0
            if param.GPIO['btn']['bottom'][1] == channel:
                self.currentModeSelected = self.currentModeSelected - 1 if self.currentModeSelected > 0 else 2

    # Stops or start the emergency
    def emergency_btn_pressed(self, channel):
        # Stops
        if self.emergency_on:
            if self.emergency_process.is_alive():
                self.emergency_process.terminate()

            self.emergency_on = False
            self.currentMenuSelected = self.HOME_MENU
            GPIO.output(param.GPIO['led']['red'][1], GPIO.LOW)
        # Starts
        else:
            self.emergency_on = True
            self.currentMenuSelected = self.EMERGENCY_MENU
            self.stop_watering()

            # If an old process exists -> terminate
            if self.emergency_process:
                if self.emergency_process.is_alive():
                    self.emergency_process.terminate()

                self.emergency_process = None

            # Creation of the new process
            self.emergency_process = multiprocessing.Process(target=self.start_emergency)
            self.emergency_process.start()

    # Adds 10 minutes to the start time
    def add_start_time(self):
        if self.startTime[0] == 23 and self.startTime[1] == 50:
            self.startTime = [0, 0]
        elif self.startTime[1] == 50:
            self.startTime[0] += 1
            self.startTime[1] = 0
        else:
            self.startTime[1] += 10

    # Removes 10 minutes to the start time
    def remove_start_time(self):
        if self.startTime[0] == 0 and self.startTime[1] == 0:
            self.startTime = [23, 50]
        elif self.startTime[1] == 00:
            self.startTime[0] -= 1
            self.startTime[1] = 50
        else:
            self.startTime[1] -= 10

    # Returns the time 23h30
    def display_time(self):
        hours = str(self.startTime[0]) if self.startTime[0] > 9 else "0" + str(self.startTime[0])
        minutes = str(self.startTime[1]) if self.startTime[1] > 9 else "0" + str(self.startTime[1])
        return hours + "h" + minutes

    # Displays the main menu
    def display_menu(self):
        self.mainMenu.get(self.currentMenuSelected)()

    # Displays the home menu
    def display_menu_home(self):
        self.configMenuSelected = 0

        today = datetime.datetime.today()
        print('----------------------')
        print('|' + '{:^20}'.format(today.strftime("%d/%m/%Y %H:%M")) + '|')
        print('|' + '{:^20}'.format('Mode ' + self.modeList[self.currentModeSelected]) + '|')

        # If mode is ON
        if self.modeList[self.currentModeSelected] == "ON":
            print('|! Arrosage infini ! |')
            print('|                    |')
        # If mode is OFF
        elif self.modeList[self.currentModeSelected] == "OFF":
            print('|Arrosage désactivé  |')
            print('|                    |')
        # If mode is AUTO
        elif self.ongoingWatering:
            print('|Arrosage en cours   |')
            print('|' + '{:^20}'.format(self.end_watering_in()) + '|')
        else:
            print('|Proch. arro. dans:  |')
            print('|' + '{:^20}'.format(self.next_watering_in()) + '|')
        print('----------------------')

    # Displays the details of the selected configuration
    def display_config_details(self):
        self.configMenu[self.configMenuSelected][0]()

        if self.configMenuSelected == self.START_STOP_WATERING_CONFIG_MENU:
            self.currentMenuSelected = self.HOME_MENU

            if self.ongoingWatering:
                self.stop_watering()
            else:
                self.start_watering()

    def display_menu_watering_days(self):
        print('----------------------')
        print('|Arrosage tous les   |')
        print('|' + '{:^20}'.format(str(self.daysBetweenWatering) + ' jours') + '|')
        print('|                    |')
        print('|<Retour        Home>|')
        print('----------------------')

    def display_menu_start_time(self):
        print('----------------------')
        print('|Arrosage à partir de|')
        print('|' + '{:^20}'.format(self.display_time()) + '|')
        print('|                    |')
        print('|<Retour        Home>|')
        print('----------------------')

    def display_menu_duration(self):
        print('----------------------')
        print('|Arrosage pendant    |')
        print('|' + '{:^20}'.format(str(self.durationOfWatering) + ' min') + '|')
        print('|                    |')
        print('|<Retour        Home>|')
        print('----------------------')

    def display_menu_mode(self):
        mode = ""
        for key, val in enumerate(self.modeList):
            if key == self.currentModeSelected:
                mode += " >" + val + "< "
            else:
                mode += " " + val.lower() + " "

        print('----------------------')
        print('|Mode d\'arrosage     |')
        print('|' + '{:^20}'.format(mode) + '|')
        print('|                    |')
        print('|<Retour        Home>|')
        print('----------------------')

    def display_config_menu(self):
        print('----------------------')
        if 1 <= self.configMenuSelected <= len(self.configMenu) - 2:
            config_menu = [self.configMenuSelected - 1, self.configMenuSelected, self.configMenuSelected + 1]
        elif self.configMenuSelected == len(self.configMenu) - 1:
            config_menu = [self.configMenuSelected - 2, self.configMenuSelected - 1, self.configMenuSelected]
        else:
            config_menu = [0, 1, 2]

        for i in config_menu:
            if i == self.configMenuSelected:
                print('|' + '{:-^20}'.format('>' + self.configMenu[i][1] + '<') + '|')
            else:
                print('|{:^20}'.format(self.configMenu[i][1]) + '|')
        print('|<Home        Select>|')
        print('----------------------')

    def display_emergency(self):
        print('----------------------')
        print('|' + '{:^20}'.format('Urgence activée !') + '|')
        print('|                    |')
        print('|' + '{:^20}'.format('Système désactivé') + '|')
        print('|                    |')
        print('----------------------')

    # Returns True if it's necessary to watering
    # Returns False if not
    def has_to_water(self):
        today = datetime.datetime.today()
        time_dif = self.get_next_watering_date() - today

        if math.ceil(time_dif.seconds / 60) == 0:
            return True

        return False

    # Returns the time before the next watering begin
    def next_watering_in(self):
        time_dif = self.get_next_watering_date() - datetime.datetime.today()

        return self.convert_time_dif_to_string(time_dif)

    # Returns the next datetime to be watered
    def get_next_watering_date(self):
        if self.lastWatering:
            next_watering_date = self.lastWatering + datetime.timedelta(days=self.daysBetweenWatering)
        else:
            next_watering_date = datetime.datetime.today()

        day = next_watering_date.strftime("%d")
        month = next_watering_date.strftime("%m")
        year = next_watering_date.strftime("%Y")
        hour = '{:02d}'.format(self.startTime[0])
        minute = '{:02d}'.format(self.startTime[1])

        return datetime.datetime.strptime(day + "/" + month + "/" + year + " " + hour + ":" + minute, "%d/%m/%Y %H:%M")

    # Returns the time until the watering is completed
    def end_watering_in(self):
        time_dif = self.endWateringDate - datetime.datetime.today()
        return self.convert_time_dif_to_string(time_dif)

    # Converts the time difference to a string
    def convert_time_dif_to_string(self, time_dif):
        seconds = time_dif.seconds
        minutes = math.floor(seconds / 60)
        hours = math.floor(minutes / 60)
        days = time_dif.days

        if days > 0:
            return str(days) + "j " + str(math.ceil(seconds / 3600)) + "h"
        elif hours > 0:
            hours = math.floor(time_dif.seconds / 3600)
            return str(hours) + "h" + '%02d' % math.ceil((seconds - hours * 3600) / 60)
        elif minutes > 0:
            return str(minutes) + " min"
        else:
            return str(seconds) + " sec"

    # Starts the watering
    def start_watering(self):
        # If the mode is OFF, cannot water
        if self.modeList[self.currentModeSelected] == "OFF":
            return

        # If the emergency is on
        if self.emergency_on:
            return

        self.ongoingWatering = True
        self.lastWatering = datetime.datetime.today()
        self.endWateringDate = self.lastWatering + datetime.timedelta(minutes=self.durationOfWatering)

        # Terminates an old process if exists
        if self.watering_process:
            if self.watering_process.is_alive:
                self.watering_process.terminate()

            self.watering_process = None

        self.watering_process = multiprocessing.Process(target=self.watering)
        self.watering_process.start()

    # Stops the watering
    def stop_watering(self):
        # If the current mode is ON, cannot stop the watering
        if self.modeList[self.currentModeSelected] == "ON" and not self.emergency_on:
            return

        if self.watering_process:
            if self.watering_process.is_alive():
                self.watering_process.terminate()

            self.watering_process = None

        self.ongoingWatering = False
        GPIO.output(param.GPIO['led']['green'][1], GPIO.LOW)

    # Blinks the LED during the watering
    def watering(self):
        green_led = param.GPIO['led']['green'][1]
        self.led_blink(green_led, 5, 0.1)

        while True:
            GPIO.output(green_led, GPIO.HIGH)
            time.sleep(1)
            GPIO.output(green_led, GPIO.LOW)
            time.sleep(1)

    # Blinks during 1 sec fast
    def led_blink(self, pin, how_much, how_fast):
        for i in range(how_much):
            GPIO.output(pin, GPIO.HIGH)
            time.sleep(how_fast)
            GPIO.output(pin, GPIO.LOW)
            time.sleep(how_fast)

    # Starts the emergency process
    def start_emergency(self):
        while True:
            GPIO.output(param.GPIO['led']['red'][1], GPIO.HIGH)
            time.sleep(1)
            GPIO.output(param.GPIO['led']['red'][1], GPIO.LOW)
            time.sleep(1)

if __name__ == '__main__':
    Watering()
