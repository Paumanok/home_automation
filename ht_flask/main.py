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

from flask import Flask, Response, request, render_template, Markup
from pymongo import MongoClient
from tabulate import tabulate

import plotly.express as px
import plotly.offline as ol
import plotly.graph_objects as go
import pandas as pd

from mongo_service import dbm

app = Flask(__name__, template_folder='templates')


sync_count = 0
start_time = 120
sync_refresh_rate = 120 #default first run value, updated values stored in mongo

presets = {"last_12":    {"disp":"Last 12 Hours", "delta": 12}, 
            "last_hour": {"disp":"Last Hour", "delta":1}, 
            "last_day":  {"disp":"Last Day", "delta":24}, 
            "last_week": {"disp":"Last Week", "delta":24*7}, 
            "last_month":{"disp":"Last Month", "delta":24*7*30}}

@app.route('/', methods= ["POST", "GET"])
def index():
    config = dbm().get_config()
    devices = dbm().get_devices()
    template_input = {
        "presets" : presets,
        "preset_keys" : presets.keys(), 
        "current_period" : config["data_period"], 
        "current_delta" : presets[config["data_period"]]["delta"],
        "refresh_delay" : str(sync_count + 5), #offset to allow new data to show
        "compensate" : config["compensate"]
    }

    if request.method == "POST":
        if "data_period" in request.form.keys():
            new_period = request.form["data_period"]
            template_input["current_period"] = new_period
            template_input["current_delta"] = presets[new_period]["delta"]
            config["data_period"] = new_period
            dbm().config.update_one({}, {"$set":{"ht_server_config":config}})
            print("changing period")
        elif "compensate" in request.form.keys():
            #only there if true
   
            config["compensate"] = True
            dbm().config.update_one({}, {"$set":{"ht_server_config":config}})
            template_input["compensate"] = True
            print("compensate")
        
        elif "compensate" not in request.form.keys():
            config["compensate"] = False
            dbm().config.update_one({}, {"$set":{"ht_server_config":config}})
            template_input["compensate"] = False
            print("notthere\n\r")

    

    datas = []
    
    for dev in devices:
        nickname = dev["nick"]
        mes = dbm().get_data_from_range(dev["MAC"], delta= template_input["current_delta"])
        times = [datetime.strptime(i["date"] + " " + i["time"], "%d/%m/%Y %H:%M:%S").isoformat() for i in mes]
        temps = compensate_temp_measurements(mes, dev, config["compensate"])#[c_to_f(i["Temp"] + dev["temp_comp"] ) for i in mes]
        hums = compensate_hum_measurements(mes, dev, config["compensate"])#[i["Humidity"] + dev["hum_comp"] for i in mes]
        data = {"nickname": nickname, "time": times, "temp": temps, "humidity": hums}
  
        datas.append(data)

    temp_fig = go.Figure(
         data = [go.Scatter(x=d["time"], y=d["temp"], name=d["nickname"], orientation='v', mode='lines') for d in datas], 
         layout = {
            'margin': {'t': 60},
           'xaxis': {'anchor': 'y', 'domain': [0.0, 1.0], 'title': {'text': 'time'}},
            'yaxis': {'anchor': 'x', 'domain': [0.0, 1.0], 'title': {'text': 'Temperature(F)'}}
         }
      )
    
    hum_fig = go.Figure(
         data = [go.Scatter(x=d["time"], y=d["humidity"], name=d["nickname"], orientation='v', mode='lines') for d in datas], 
         layout = {
            'margin': {'t': 60},
           'xaxis': {'anchor': 'y', 'domain': [0.0, 1.0], 'title': {'text': 'time'}},
            'yaxis': {'anchor': 'x', 'domain': [0.0, 1.0], 'title': {'text': 'Humidity(%)'}}
         }
      )

    

    template_input["temp_plot"] = Markup(ol.plot(temp_fig, output_type='div', include_plotlyjs=False))
    template_input["hum_plot"] = Markup(ol.plot(hum_fig, output_type='div', include_plotlyjs=False))


    return render_template('index.html', t_input = template_input)
        
   

@app.route('/next', methods=["GET"])
def next_measurement():  
    return "sync_time " + str(sync_count)

@app.route('/config', methods=["GET", "POST"])
def config():
    db = dbm()
    devices = db.devices.find({},{"_id":0})
    config = db.get_config()
  
    
    if request.method == "POST":
        for key in request.form.keys():
            if key == "save_config":
                db.save_config()

            if key in config.keys():
                config[key] = request.form[key]
                db.config.update_one({}, {"$set" : {"ht_server_config" : config}})


            for dev in devices:
                
                if dev["MAC"] in key:
                    
                    parsed = key.split("-")
                    
                    if len(parsed) > 1:
                        print("parsing key")
                        field = parsed[1]
                        
                        db.devices.update_one({"MAC": dev["MAC"]}, {"$set":{field:request.form[key]}})

                   
                    
                    
    
    
    dbsize = get_db_size_str(db)
    devices = db.get_devices()
    config = db.get_config()    
    return render_template('config.html', dev_list=devices, config=config, db_size=dbsize)


@app.route('/mongo_dump', methods=["GET"])
def mongo_dump():
    db=dbm()
    ret_str = "<body><p>"
    to_return =  db.dump_data()
    for device in to_return["devices"]:

        dataset = device["measurements"]
        header = dataset[0].keys()
        rows = [x.values() for x in dataset]
        dev_mac = device["MAC"]
        dev_nick = device["nick"]
        ret_str = ret_str + f"Device Mac: {dev_mac}, nickname: {dev_nick}\r\n"
        ret_str = ret_str + tabulate(rows, header, tablefmt="html")
        ret_str = ret_str + "\r\n</p></body>"

    return ret_str

@app.route('/test_dump', methods=["GET"])
def testdump():
    dtnow= datetime.now()
    
    dt_prior = dtnow - timedelta(days=1)
    #devs = dbm().get_devices()
    devs = dbm().devices.find({},{"_id":False})
    ret_str = ""
    dataset = dict()
    for dev in devs:
        #dataset[dev["MAC"]] = dbm().get_data_from_range(dev["MAC"], dtnow, dt_prior, reverse=False)
        del dev["measurements"]
        dataset[dev["MAC"]] = dev
    return dataset

@app.route('/data',methods=["POST", "GET"])
def data():
    db = dbm().db
    dev = dbm().devices
    measurements = dbm().measurements

    if request.method == "GET":
        return "hello"

    if request.is_json:
        now = datetime.now()
        dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
        dt_date= now.strftime("%d/%m/%Y")
        dt_time = now.strftime("%H:%M:%S")
        to_insert = {"date":dt_date, "time": dt_time, "MAC": request.json["mac"], "Temp": request.json["temp"], "Humidity": request.json["hum"]}
        print("====================\r\nDATA_RECIEVED: \r\n" + str(to_insert) + "\r\n====================")

        resp = measurements.insert_one(to_insert.copy())
        
        if resp.acknowledged == True:
            
            device_res =  dev.find_one({"MAC":request.json["mac"]} )
            
            if device_res != None:
                print("updating")
                dev.update_one({"MAC":request.json["mac"]}, { "$push": {"measurements": resp.inserted_id}})
            else:
                print("inserting")
                dev.insert_one({"MAC": request.json["mac"], "nick": "", "measurements": [resp.inserted_id]})
        
        data2 = request.json
        print(data2)
    print("time-to-sync: " + str(sync_count))
    return "200"


# Helper functions
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

def get_db_size_str(db):
    size = int(db.db.command("collstats", "measurements")["size"])
    if size > 1000000000:
        dbsize = "{0} Gb".format(size/1000000)
    elif size > 1000000:
        dbsize = "{0} Mb".format(size/1000000)
    elif size > 1000:
        dbsize = "{0} kb".format(size/1000) 
    else:
        dbsize = "{0} b".format(size)

    return dbsize

def sync_timer():
    global sync_refresh_rate
    global sync_count
    while True:
        sync_count = dbm().get_refresh_rate()

        while sync_count > 0:
            sync_count -= 1
            time.sleep(1)


def init_sync_timer():
    #Initialize the sync rate to work with settings
    global sync_refresh_rate
    #conf_cursor = dbm().config.find_one({})
    #cursor_len = len(list(dbm().config.find({})))   
    config = dbm().get_config()
    
    if "m_sync_refresh_rate" in config.keys():      
        sync_refresh_rate = config["m_sync_refresh_rate"]
        print("====== Configured Refresh Rate: " + str(sync_refresh_rate) + " seconds")
        
    #configure the thread
    t = threading.Thread(target=sync_timer)
    t.daemon = True
    return t

if __name__ == "__main__":
    measurement_sync = init_sync_timer()
    measurement_sync.start()
    print(dbm().get_config()["startup_message"])
    #to_remove = []
    #[dbm().config.update_many({}, {"$unset": {i:""}}) for i in to_remove]

    app.run(host="0.0.0.0", port="5000",debug=True)
