"""
main.py

Flask server for supporting ESP32 devices with BME280 measurement sensors and serving
the data collected to a local network.

Author: Matthew Smith

"""
import json
import threading
import time
from datetime import datetime, timedelta
from io import BytesIO

from flask import Flask, Response, request, render_template, Markup, send_file
from pymongo import MongoClient
from tabulate import tabulate

import plotly.express as px
import plotly.offline as ol
import plotly.graph_objects as go
import plotly.subplots as subplots
import plotly.io as pio
#import pandas as pd

from mongo_service import dbm, Configuration

app = Flask(__name__, template_folder='templates')


sync_count = 0
start_time = 120
sync_refresh_rate = 120 #default first run value, updated values stored in mongo

@app.route('/', methods=["POST","GET"])
def home():
    config = Configuration(dbm())

    if request.method == "POST":
        req_keys = request.form.keys()
        if "data_period" in req_keys:
            config.set_and_push("data_period", request.form["data_period"])
        else:
            if "compensate" in req_keys:
                config.set_and_push("compensate", True)
            elif "compensate" not in req_keys:
                config.set_and_push("compensate", False) 

    dev_data = collect_measurements(config)
    if len(dev_data) < 1:
        return "error" #lol this needs to be addressed

    temp_fig = go.Figure(
            data = [go.Scatter(x=d["time"], y=d["temp"], name=d["nickname"], orientation='v', mode='lines') for d in dev_data], 
            layout = {
                'margin': {'t': 60},
                'xaxis': {'anchor': 'y', 'domain': [0.0, 1.0], 'title': {'text': 'time'}},
                'yaxis': {'anchor': 'x', 'domain': [0.0, 1.0], 'title': {'text': 'Temperature(F)'}}
            }
        )
        
    hum_fig = go.Figure(
            data = [go.Scatter(x=d["time"], y=d["humidity"], name=d["nickname"], orientation='v', mode='lines') for d in dev_data], 
            layout = {
                'margin': {'t': 60},
                'xaxis': {'anchor': 'y', 'domain': [0.0, 1.0], 'title': {'text': 'time'}},
                'yaxis': {'anchor': 'x', 'domain': [0.0, 1.0], 'title': {'text': 'Humidity(%)'}}
            }
        )

    ordered_keys = list(config.presets.keys())
    current_period = config.data_period
    ordered_keys.remove(current_period)
    ordered_keys.insert(0,current_period)
    template_input = {
        "presets" : config.presets,
        #"preset_keys" : config.presets.keys(), 
        "preset_keys" : ordered_keys, 
        "current_period" : config.data_period, 
        "current_delta" : config.get_cur_delta(),
        "refresh_delay" : str(sync_count + 5), #offset to allow new data to show
        "compensate" : config.compensate
    }

    template_input["temp_plot"] = Markup(ol.plot(temp_fig, output_type='div', include_plotlyjs=False))
    template_input["hum_plot"] = Markup(ol.plot(hum_fig, output_type='div', include_plotlyjs=False))

    return render_template('index.html', t_input = template_input)

@app.route('/images', methods=['GET'])
def get_images():
    config = Configuration(dbm())

    dev_data = collect_measurements(config)
    if len(dev_data) < 1:
        return "error" #lol this needs to be addressed

    fig = subplots.make_subplots(rows=2, cols=1)

    fig.add_traces(
        data = [go.Scatter(x=d["time"], y=d["temp"], name=d["nickname"], orientation='v', mode='lines', legendgroup="a") for d in dev_data], 
        rows=1, cols=1
        
    )
    fig.add_traces(
        data = [go.Scatter(x=d["time"], y=d["humidity"], name=d["nickname"], orientation='v', mode='lines', legendgroup="a", showlegend=False) for d in dev_data], 
        rows=2, cols=1
    )

    ret_image = pio.to_image(fig)

    return send_file(
        BytesIO(ret_image),
        mimetype='image/png',
        as_attachment=False,
        download_name='%s.png' % datetime.now().strftime("%H:%M:%S"))

@app.route('/next', methods=["GET"])
def next_measurement():  
    return "sync_time " + str(sync_count)


@app.route('/config', methods=["GET", "POST"])
def config():
    config = Configuration(dbm())

    if request.method == "POST":
        for key in request.form.keys():
            if key == "save_config":
                config.save_config()
            
            if key in config.keys():
                print(config)
                config.set_and_push(key, request.form[key])

            for dev in config.devices:
                if dev["MAC"] in key:
                    parsed = key.split("-")
                    if len(parsed) > 1:
                        field = parsed[1]
                        config.set_device_attr(dev["MAC"], field, request.form[key])
                        
    dbsize = dbm().get_db_size_str()
    return render_template('config.html', dev_list=config.devices, config=config.config_dict, db_size=dbsize)


@app.route('/test_dump', methods=["GET"])
def testdump():
    config = Configuration(dbm())
    dataset = dict()
    for dev in config.devices:
        dev["measurements"] = dbm().get_data_from_range(dev["MAC"])
        dataset[dev["MAC"]] = dev
    return dataset

#Actual interface esp32 communicates with.
@app.route('/data',methods=["POST", "GET"])
def data():
    db = dbm().db
    dev = dbm().devices
    measurements = dbm().measurements

    if request.method == "GET":
        return "hello"

    if request.is_json:
        now = datetime.now()
        to_insert = {"date":now.strftime("%d/%m/%Y"),
                 "time":now.strftime("%H:%M:%S"),
                 "MAC": request.json["mac"], 
                 "Temp": request.json["temp"], 
                 "Humidity": request.json["hum"]}

        print("\r\nDATA_RECIEVED: \r\n" + str(to_insert) + "\r\n")

        resp = measurements.insert_one(to_insert.copy())        
    #print("time-to-sync: " + str(sync_count))
    return "200"


# Helper functions
def collect_measurements(config):
    dev_data = []

    for dev in config.devices:
        measurements = dbm().get_data_from_range(dev["MAC"], delta=config.get_cur_delta())
        data = {"nickname": dev["nick"],
                "time": [datetime.strptime(i["date"] + " " + i["time"], "%d/%m/%Y %H:%M:%S").isoformat() for i in measurements],
                "temp": compensate_temp_measurements(measurements, dev, config.compensate),
                "humidity": compensate_hum_measurements(measurements, dev, config.compensate)}

        dev_data.append(data)

    return dev_data

def compensate_temp_measurements(measurements, device, compensate=False):
    comp = 0
    if compensate:
        comp = float(device["temp_comp"])
    temps = [(c_to_f(i["Temp"]) + float(comp) ) for i in measurements]
    return temps

def compensate_hum_measurements(measurements, device, compensate=False):
    comp = 0
    if compensate:
        comp = float(device["hum_comp"])
    hums = [(i["Humidity"] + comp) for i in measurements]
    return hums

def c_to_f(c):
    return (c * 9/5) + 32
# end helper


#Syncronization for devices and home refresh
def sync_timer():
    global sync_refresh_rate
    global sync_count
    config = Configuration(dbm())
    while True:
        sync_count = int(config.m_sync_refresh_rate)

        while sync_count > 0:
            sync_count -= 1
            time.sleep(1)


def init_sync_timer():
    #Initialize the sync rate to work with settings
    global sync_refresh_rate
    
    config = Configuration(dbm())
    if "m_sync_refresh_rate" in config.keys():      
        sync_refresh_rate = config.m_sync_refresh_rate
        print("====== Configured Refresh Rate: " + str(sync_refresh_rate) + " seconds")
    #else use hardcoded default

    #configure the thread
    t = threading.Thread(target=sync_timer)
    t.daemon = True
    return t

if __name__ == "__main__":
    measurement_sync = init_sync_timer()
    measurement_sync.start()
    print(Configuration(dbm()).startup_message)
    app.run(host="0.0.0.0", port="5000",debug=True)
