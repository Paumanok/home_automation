from pymongo import MongoClient
import json
import copy
import os

class dbm:

    def __init__(self):
        self.client = MongoClient('mongodb://' + os.environ['MONGODB_HOSTNAME'] +  ':27017/')

        self.db = self.client['ht_db']
        self.devices = self.db["devices"]
        self.measurements = self.db["measurements"]
        self.config = self.db['config']

        #initial config loading if it hasn't been loaded before
        
        if len(list(self.config.find({}))) == 0:
            with open('/flask_app/default/config.json', 'r') as cf_file:
                def_config = json.load(cf_file)
                self.config.insert_one(def_config)

    def get_devices(self):
        dev_cursor = self.devices.find({},{"_id":0})
        devices = []
        for dev in dev_cursor:
            dev_dict = dict()
            dev_dict["MAC"] = dev["MAC"]
            dev_dict["nick"] = dev["nick"]
            devices.append(dev_dict)
            
        return devices

    def get_config(self):
        conf = self.config.find_one({}, {"_id":0})
        if conf != None:
            return conf["ht_server_config"]
        
        

    def dump_data(self):
        dev_cursor = self.devices.find({},{"_id":0})
        devs = {"devices": []}
        for dev in dev_cursor:
            dev_dict = dict()
            dev_dict["MAC"] = dev["MAC"]
            dev_dict["nick"] = dev["nick"]
            dev_dict["measurements"] = []

            for ob_id in dev["measurements"]:
                #print(ob_id)
                mes = self.measurements.find_one({"_id":ob_id}, {"_id": 0})
                #print(mes)
                dev_dict["measurements"].append(mes)
            #print(dev)
            devs["devices"].append(dev_dict)
        #print(devs)
        return devs
