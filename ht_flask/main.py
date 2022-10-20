from pkg_resources import DEVELOP_DIST
from flask import Flask, Response, request, render_template
import json
from datetime import datetime, timedelta
import threading
import time
from mongo_service import dbm
from pymongo import MongoClient
from tabulate import tabulate
from jinja2 import Environment, FileSystemLoader

app = Flask(__name__, template_folder='templates')

results = []

sync_count = 0
start_time = 120
sync_refresh_rate = 120 #default first run value, updated values stored in mongo

@app.route('/', methods= ["POST", "GET"])
def index():
    if request.method == "GET":
        return "hello world"
    if request.method == "POST":
        data = request.json
        print(data)
        print(request.get_data)
        #print(json.dumps(request.json))
        return "200"

@app.route('/next', methods=["GET"])
def next_measurement():  
    return "sync_time " + str(sync_count)

@app.route('/config', methods=["GET", "POST"])
def config():
    db = dbm()
    devices = db.get_devices()
    config = db.get_config()
  
    if request.method == "POST":
        for key in request.form.keys():
            if key in config.keys():
                config[key] = request.form[key]
                db.config.update_one({}, {"$set" : {"ht_server_config" : config}})


            for dev in devices:
                if key == dev["MAC"]:
                    print("found it")
                    print(request.form[key])
                    db.devices.update_one({"MAC": dev["MAC"]}, {"$set":{"nick": request.form[key]}})
        

    devices = db.get_devices()
    config = db.get_config()    
    return render_template('config.html', dev_list=devices, config=config)


@app.route('/nickname', methods=["GET", "POST"])
def nickname_config():
    db=dbm()
    devices = db.get_devices()
    if request.method == "GET":
        #environment = Environment(loader=FileSystemLoader("templates/"))
        #template = environment.get_template("nicknames.html")
        content = render_template('nicknames.html', dev_list=devices)
        return content
    
    if request.method == "POST":
        print(request)
        print("hit")
        print(request.form.keys())
        for key in request.form.keys():
            for dev in devices:
                if key == dev["MAC"]:
                    print("found it")
                    print(request.form[key])
                    db.devices.update_one({"MAC": dev["MAC"]}, {"$set":{"nick": request.form[key]}})
        devices = db.dump_data()["devices"]
        return render_template("nicknames.html", dev_list=devices)

@app.route('/mongo_dump', methods=["GET"])
def mongo_dump():
    db=dbm()
    ret_str = "<body><p>"
    to_return =  db.dump_data()
    for device in to_return["devices"]:
        #print(device)
        dataset = device["measurements"]
        header = dataset[0].keys()
        rows = [x.values() for x in dataset]
        dev_mac = device["MAC"]
        dev_nick = device["nick"]
        ret_str = ret_str + f"Device Mac: {dev_mac}, nickname: {dev_nick}\r\n"
        ret_str = ret_str + tabulate(rows, header, tablefmt="html")
        ret_str = ret_str + "\r\n</p></body>"
    #print(ret_str)
    return ret_str

@app.route('/test_dump', methods=["GET"])
def testdump():
    dtnow= datetime.now()
    now = dtnow.strftime("%d/%m/%Y %H:%M:%S")
    dt_prior = dtnow - timedelta(days=1)
    day_prior = dt_prior.strftime("%d/%m/%Y %H:%M:%S")
    devs = dbm().get_devices()
    ret_str = ""
    dataset = dict()
    for dev in devs:
        dataset[dev["MAC"]] = dbm().get_data_from_range(dev["MAC"], dtnow, dt_prior, reverse=False)
        # ret_str += "<body><p>"
        # dev_mac = dev["MAC"]
        # dev_nick = dev["nick"]
        # header = dev.keys()
        # rows = [x.values() for x in dataset]
        # ret_str = ret_str + f"Device Mac: {dev_mac}, nickname: {dev_nick}\r\n"
        # ret_str = ret_str + tabulate(rows, header, tablefmt="html")
        # ret_str = ret_str + "\r\n</p></body>"
    return dataset

@app.route('/data',methods=["POST", "GET"])
def data():
    db = dbm().db
    dev = dbm().devices
    measurements = dbm().measurements

    if request.method == "GET":
        return str(results)
        #return json.dumps(results)

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
    conf_cursor = dbm().config.find_one({})
    cursor_len = len(list(dbm().config.find({})))
    
    if cursor_len > 0:      
        sync_refresh_rate = conf_cursor["ht_server_config"]["m_sync_refresh_rate"]
        print("====== Configured Refresh Rate: " + str(sync_refresh_rate) + " seconds")
        
    #configure the thread
    t = threading.Thread(target=sync_timer)
    t.daemon = True
    return t

if __name__ == "__main__":
    measurement_sync = init_sync_timer()
    measurement_sync.start()
    print(dbm().get_config()["startup_message"])

    app.run(host="0.0.0.0", port="5000",debug=True)
