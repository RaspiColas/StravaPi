#!/usr/bin/python3
# -*- coding: utf-8 -*-

#---------------------------------------------------#
#													#
#				stravapi.py		        			#
#				by N.Mercouroff						#
#													#
#---------------------------------------------------#

"""
Program to display Strava activities on an Inky display (e-paper) on a PiZeroW

Version 23/Dec/22

To run it:
	python /home/pi/Strava/stravapi.py -v
-v is for verbose mode

Needs in /home/pi/Strava/strava.conf:
	[STRAVAAPI]
	client_id=YOUR_CLIENT_ID
	client_secret=YOUR_TOKEN
	[CONFIG]
	start=START_DATE
	pixel_per_km=PIXEL
	activity_type=ACTIVITY
with:
	YOUR_CLIENT_ID: Strava client ID
	YOUR_TOKEN: Strava secret token
	START_DATE: Starting date for retrieving strava data (eg, 2022-09-01T00:00:00Z)
	PIXEL: Number of pixels in the bar per km of ativity (e.g., 1.5)
	ACTIVITY: The type of activity to plot (eg, Run)

Generates files:
	log_strava.log: Log file
	strava-token.json: Strava token file
	strava-token.json.bak: Previous Strava token file
	YEAR-monthly-strava.csv: Total km per month for year YEAR

"""

from datetime import date, timedelta
import stravalib  # sudo pip install stravalib
import math  # sudo pip install numpy
from time import strftime
import sys
import json
from os import path, system
import inkyphat
from PIL import ImageFont  # pip install font-fredoka-one
import ConfigParser
from datetime import datetime

request_token = "curl -X POST https://www.strava.com/api/v3/oauth/token -d client_id=%s -d client_secret=%s -d grant_type=refresh_token -d refresh_token=%s > %s"


PATH_PREFIX = path.dirname(path.abspath(__file__)) + '/'
LOG_FILENAME = PATH_PREFIX + "log_strava.log"
STRAVA_TOKEN_FILE = PATH_PREFIX + "strava-token.json"
CONFIG_FILENAME = PATH_PREFIX + 'strava.conf'

KM_FILENAME = PATH_PREFIX + "%s-monthly-strava.csv"

totaldistance = 0
intensite = 0.25
bargraph = []
monthly_distance = {}
totaldistance = 0
totalactivity = 0
day_nb = 34
row_nb = 7
# each pixel in the chart represents this many km in the activity, rounded up to the next pixel
# km_per_pixel = 0.5
# pixel_per_km = 2
km_sl = 40

WIDTH = 212
HEIGHT = 104
TEXT_OFFSET = 0

font18 = inkyphat.ImageFont.truetype(inkyphat.fonts.FredokaOne, 18)
font20 = inkyphat.ImageFont.truetype(inkyphat.fonts.FredokaOne, 20)
font24 = inkyphat.ImageFont.truetype(inkyphat.fonts.FredokaOne, 24)

font_size = font18

inkyphat.set_rotation(180)

verbose = False
param = {}

#-------------------------------------------------
#		Utilities
#-------------------------------------------------


def tolog(txt, forceprint=False):
	"""
		Logs events and prints it if forceprint = True
	"""
	if verbose or forceprint:
		print(txt)
	now = strftime('%Y/%m/%d %H:%M:%S')
	msg = "%s\t%s" % (now, txt)
	with open(LOG_FILENAME, 'a') as file:
		file.write(msg + "\n")
	return


#-------------------------------------------------
#		Read config
#-------------------------------------------------

def get_conf():
	global param

	tolog("Loading the configuration file...")
	try:
		config = ConfigParser.ConfigParser()
		config.read(CONFIG_FILENAME)

		param["client_id"] = config.get('STRAVAAPI', 'client_id')
		param["client_secret"] = config.get('STRAVAAPI', 'client_secret')
		param["start_date"] = config.get('CONFIG', 'start')
		param["pixel_per_km"] = float(config.get('CONFIG', 'pixel_per_km'))
		param["activity_type"] = config.get('CONFIG', 'activity_type')
		tolog("...success loading config")
		return True

	except Exception as e:
		tolog('Error reading config file %s: %s' % (CONFIG_FILENAME, e), True)
		return False


#-------------------------------------------------
#		Inky functions
#-------------------------------------------------

def clear_display():
	inkyphat.clear()
	return


def draw_rect(x1, y1, x2, y2, f=inkyphat.BLACK, o=inkyphat.BLACK):
	inkyphat.rectangle([x1, y1, x2, y2], fill=f, outline=o)
	return


def draw_line(x1, y1, x2, y2, o=inkyphat.BLACK):
	inkyphat.line((x1, y1, x2, y2), o)
	return


def draw_text(x1, y1, text, f=inkyphat.WHITE, ft=font_size):
	inkyphat.text((x1, y1), text, f, ft)
	return


def display_show():
	inkyphat.show()
	return True


def display_title(text):
	tolog("Display title: %s" % (text))
	clear_display()
	draw_rect(0, 0, 212, 30, inkyphat.RED, inkyphat.RED)
	width, height = font_size.getsize(text)
	d, r = divmod(width, 2)
	draw_text(106-d, 3, text, inkyphat.WHITE, font_size)
	return True


def drawgraph():
	today = date.today()
	last = len(bargraph) - 1

	for val in range(4):
		draw_line(207 - day_nb * 6, 100 - 20*val, 209 - day_nb * 6, 100 - 20*val)

	for col in range(day_nb):
		day = today - timedelta(days=col)
		l = 200 - col * 6
		if day.day == 1:
			draw_line(l, 100, l, 75)
		elif day.weekday() == 6:
			draw_line(l + 7, 100, l + 7, 90)
		else:
			draw_line(l + 7, 100, l + 7, 98)
		if str(day) in bargraph[last]['date']:
			val = bargraph[last]['val']
			r = max(30, 100 - val * param["pixel_per_km"])
			if val > km_sl:
				draw_rect(l+3, r, l+5, 100, inkyphat.RED, inkyphat.RED)
			else:
				draw_rect(l+3, r, l+5, 100)
			last -= 1
			if last < 0:
				break
	draw_line(207 - day_nb * 6, 100, 207 - day_nb * 6, 98)

	return


#-------------------------------------------------
#		Strava input
#-------------------------------------------------


def load_activities(activities):
	global totaldistance, bargraph, totalactivity, monthly_distance

	tolog("Loading activities...")
	bargraph = []
	totaldistance = 0
	date_last = ''
	current_month = datetime.now().month
	current_year = datetime.now().year
	try:
		for activity in activities:
			tp = activity.type
			dt = activity.start_date
			date = str(dt)
			if not tp == param["activity_type"]:
				tolog("Skipping date %s as type is %s" %(date, tp))
				continue
			distance = float(stravalib.unithelper.kilometers(activity.distance))
			val = int(math.ceil(distance * param["pixel_per_km"]))

			if dt.year == current_year:
				try:
					monthly_distance[dt.month] += distance
				except:
					monthly_distance[dt.month] = distance

			if dt.month == current_month:
				totaldistance += distance
				totalactivity += 1
			tolog("%s: %.1f (%s px) %s" % (date, distance, val, tp))
			if date[:10] == date_last[:10]:
				bargraph[-1]['val'] += val
			else:
				graph = {
					'date': date,
					'val': val
				}
				bargraph.append(graph)
				date_last = date
		tolog("...loading activity success, total distance = %s" % (totaldistance))
		return True
	except Exception as e:
		tolog("...loading activity error %s" % (e))
		return False


def get_token():
	with open(STRAVA_TOKEN_FILE, 'r') as f:
		resp_json = json.loads(f.read())
	return resp_json['refresh_token'], resp_json['access_token']


def getstravabargraph():
	refresh_tok, access_tok = get_token()
	try:
		client = stravalib.client.Client(access_token=access_tok)
		activitiesthisyear = client.get_activities(after=param["start_date"], limit=500)  # Download all activities after startdate

		if load_activities(activitiesthisyear):
			return True
		else:
			return False
	except Exception as e:
		tolog("Strava returned error %s" % (e))
		tolog("Regenerating refresh token...")
		try:
			cmd = request_token % (
				param["client_id"], param["client_secret"], refresh_tok, STRAVA_TOKEN_FILE)
			system("cp %s %s.bak" % (STRAVA_TOKEN_FILE, STRAVA_TOKEN_FILE))
			system(cmd)
			refresh_tok, access_tok = get_token()
			client = stravalib.client.Client(access_token=access_tok)
			activitiesthisyear = client.get_activities(
				after=param["start_date"], limit=500)  # Download all activities after startdate
			if load_activities(activitiesthisyear):
				return True
			else:
				return False
		except Exception as e:
			tolog("Strava returned error %s" % (e), True)
			tolog("Cannot regenerate token, sorry")
			if path.getsize(STRAVA_TOKEN_FILE) == 0:
				system("cp %s.bak %s" % (STRAVA_TOKEN_FILE, STRAVA_TOKEN_FILE))
				tolog("Token file copied back")
			return False


#-------------------------------------------------
#		Ecriture des données
#-------------------------------------------------

def write_km():
	global monthly_distance

	tolog("Saving the km file...")

	try:
		filename = KM_FILENAME % (datetime.now().year)
		with open(filename, 'w') as km_file:
			for month in monthly_distance:
				tolog("Writing %s km for month %s" %
				      (monthly_distance[month], month))
				km_file.write("%s\t%s\n" % (month, monthly_distance[month]))

		tolog("...success saving km in %s" % (filename))
		return True

	except Exception as e:
		tolog('Error saving km file %s: %s' % (KM_FILENAME, e), True)
		return False



#-------------------------------------------------
#		Main function for shell command
#-------------------------------------------------

def main():
	ok = getstravabargraph()  # Get an initial load from Strava
	if not ok:
		return False
	msg = "Collected %s km for %s activities this month" % (
		totaldistance, totalactivity)
	tolog(msg, True)
	current_month = datetime.now().month
	title = "%.0f km depuis le 1/%s" % (totaldistance, current_month)
	clear_display()
	display_title(title)
	drawgraph()
	display_show()
	write_km()
	return True


if __name__ == "__main__":

	verbose = (len(sys.argv) == 2)
	if verbose:
		tolog("Verbose mode")

	tolog("=== Strava start ===")
	ok = get_conf()
	if not ok:
		tolog("=== Load of Strava configuration finished unsuccessfuly ===")
		exit()
	ok = main()
	if ok:
		tolog("=== Strava finished successfuly ===")
	else:
		tolog("=== Strava finished unsuccessfuly ===")

#-------------------------------------------------
#----- FIN DU PROGRAMME --------------------------
#-------------------------------------------------
