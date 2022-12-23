# StravaPi
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
