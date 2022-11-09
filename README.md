# home_automation

This project isn't really(yet) doing any automation of any kind. 

This began as a proof of concept for making my own temp/humidity tracker to keep my
antique guitar safe from sharp drops in humidity. Paired with this project are several
ESP-32 devices with BME280 sensors. They simply take a measurement, send the measurement, 
and check for the next time the server expects a measurement. 


It's a basic flask server + mongodb, with some practice in html, jinja templates, and
python patterns to abstract the database operations away. 

I wrote this to work with n-clients, expandable as needed and not fussy if a device was to
go down. 

It can currently serve me plots of the collected data from a selected time frame, in HTTP or
in a pre-made image that I use in conjuction with my python bot to serve me a overview when 
I'm away from home. Additionally, I can configure individual device profiles and apply compensation
offsets to each device's temp/humidity measurements. You will never know the true temperature
of your living room, but at least you can get each device telling you the same wrong temperature. 