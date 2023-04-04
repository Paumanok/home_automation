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

    temp_fig = generate_plot(dev_data, "temp", "Temperature(F)")
    hum_fig = generate_plot(dev_data, "humidity", "Humidity(%)")

    #TODO I need to create a way to determine what each sensor supports 
    pres_fig = generate_plot(dev_data, "Pressure", "Ambient Pressure(hPa)")
    pm_fig = generate_plot(dev_data, "pm25", "pm25")

    #pressure_fig = generate_plot(dev_data, "Pressure", "hPa")

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
    template_input["pres_plot"] = Markup(ol.plot(pres_fig, output_type='div', include_plotlyjs=False))
    template_input["pm_plot"] = Markup(ol.plot(pm_fig, output_type='div', include_plotlyjs=False))

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
        data = [go.Scatter(x=d["time"], y=d["humidity"], name=d["nickname"], orientation='v', mode='lines', legendgroup="a") for d in dev_data], 
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

@app.route('/get_last_measurement', methods=["GET"])
def get_last_measurement():
    config = Configuration(dbm())
    
    ret = dict()
    for dev in config.devices:
        meas = dbm().get_last_measurements(dev["MAC"])
        if type(meas) is dict:
            dev["measurements"] = meas
        else:
            continue
        ret[dev["nick"]] = dev

    current_time = datetime.now()
    for key in list(ret.keys()):
        if isinstance(ret[key], dict) and "measurements" in ret[key]:
            item_time_str = ret[key]["measurements"]["date"] + " " + ret[key]["measurements"]["time"]
            item_time = datetime.strptime(item_time_str, "%d/%m/%Y %H:%M:%S")
            if (current_time - item_time).total_seconds() > 120:
                del ret[key]
    return ret


    ret["next_refresh"] = sync_count #this bit of api is not very standard, but its useful!
    
    return ret


@app.route('/config', methods=["GET", "POST"])
def config():
    config = Configuration(dbm())

    if request.method == "POST":
        for key in request.form.keys():
            if key == "save_config":
                config.save_config()
            
            if key in config.keys():
                print(config, flush=True)
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
    config = Configuration(dbm())

    if request.method == "GET":
        return "hello"

    if request.is_json:
        now = datetime.now()
        to_insert = {"date":now.strftime("%d/%m/%Y"),
                 "time":now.strftime("%H:%M:%S"),
                 "MAC": request.json["mac"], 
                 "Temp": request.json["temp"], 
                 "Humidity": request.json["hum"]}
        
        if "pressure" in request.json.keys():
            to_insert["Pressure"] = request.json["pressure"]

        if "pm25" in request.json.keys():
            to_insert["pm25"] = request.json["pm25"]

        #check if a config section for the device exists
        if request.json["mac"] not in [dev["MAC"] for dev in config.devices]:
            config.add_device_to_config(request.json["mac"])

        print("\r\nDATA_RECIEVED: \r\n" + str(to_insert) + "\r\n", flush=True)

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

        if len(measurements) > 0: #don't upset sleepign sensors
            if "Pressure" in measurements[0].keys():
                data["Pressure"]= scale_pressure_measurements(measurements)
        
            if "pm25" in measurements[0].keys():
                
                data["pm25"] = [i["pm25"] for i in measurements if "pm25" in i.keys()]

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

def scale_pressure_measurements(measurements):
    pres = [(i["Pressure"] / 100) for i in measurements]
    return pres

def c_to_f(c):
    return (c * 9/5) + 32

def generate_plot(in_data, data_key, data_label):
    
    approved_data = []
    for d in in_data:
        if data_key in d.keys():
            approved_data.append(d)

    figure = go.Figure(
            data = [go.Scatter(x=d["time"], y=d[data_key], name=d["nickname"], orientation='v', mode='lines') for d in approved_data], 
            layout = {
                'margin': {'t': 60},
                'xaxis': {'anchor': 'y', 'domain': [0.0, 1.0], 'title': {'text': 'time'}},
                'yaxis': {'anchor': 'x', 'domain': [0.0, 1.0], 'title': {'text': data_label}}
            }
        )

    return figure
# end helper


#Syncronization for devices and home refresh
def sync_timer():
    global sync_refresh_rate
    global sync_count
    config = Configuration(dbm())
    while True:
        config.load_config() #refresh dict from db, config object gets stale
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
