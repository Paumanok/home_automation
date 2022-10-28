"""
mongo_service.py
utility for wranglin' mongo, primarily helper functions to support the main flask server
author: Matthew Smith
"""

from pymongo import MongoClient
from bson import objectid
import json
import copy
import os
from datetime import datetime, timedelta, timezone

default_config_path = '/flask_app/default/config.json'

class dbm:

    def __init__(self):
        self.client = MongoClient('mongodb://' + os.environ['MONGODB_HOSTNAME'] +  ':27017/')

        self.db = self.client['ht_db']
        self.devices = self.db["devices"]
        self.measurements = self.db["measurements"]
        self.config = self.db['config']

        #initial config loading if it hasn't been loaded before
        
        if len(list(self.config.find({}))) == 0:
            with open(default_config_path, 'r') as cf_file:
                def_config = json.load(cf_file)
                self.config.insert_one(def_config)

    def get_devices(self):
        dev_cursor = self.devices.find({},{"_id":0})
        devices = []
        for dev in dev_cursor:
            dev_dict = dict()
            dev_dict["MAC"] = dev["MAC"]
            dev_dict["nick"] = dev["nick"]
            dev_dict["temp_comp"] = dev["temp_comp"]
            dev_dict["hum_comp"] = dev["hum_comp"]
            devices.append(dev_dict)
            
        return devices

    def get_config(self):
        conf = self.config.find_one({}, {"_id":0})
        if conf != None:
            return conf["ht_server_config"]

    def save_config(self, filepath=default_config_path):
        conf = self.config.find_one({}, {"_id":0})
        if conf != None:
            cur_config = conf
            with open(filepath, 'w+') as cf_file:
                json.dump(cur_config, cf_file, indent=4)



    def get_refresh_rate(self):
        refresh_rate = self.get_config()["m_sync_refresh_rate"]
        return int(refresh_rate)

    def get_data_from_range(self, mac_addr, delta=12):
        #from_datetime will assume time is in UTC, adjust .now() so we don't get an extra 4 hours
        dummy_id = objectid.ObjectId.from_datetime(datetime.now(timezone.utc) - timedelta(hours=delta))
        print(datetime.now() - timedelta(hours=delta))
        measurements = self.measurements.find({"_id": {"$gte": dummy_id}, "MAC": mac_addr}, {"_id":0})
        
        data = [i for i in measurements]
        
        return data


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

#class to standardize the config access
class configuration:
    MIN_REFRESH_RATE = 0
    MAX_REFRESH_RATE = 1000

    def __init__(self, db):
        _db = db
        _config_collection = db['config']
        self.load_config()

    def __getattr__(self, name):
        if name in self.config.keys():
            return self.config[str(name)]
        else:
            return None

    def __setattr__(self, __name: str, __value) -> None:
        if __name in self.config.keys():
            if __name == "m_sync_refresh_rate":
                if __value < self.MIN_REFRESH_RATE or __value > self.MAX_REFRESH_RATE:
                    return
            self.config[__name] = __value

    def __repr__(self) -> str:
        return json.dumps(self.config, indent=4)

    def set_and_push(self, key, value):
        self.config[key] = value
        self.push_config()

    #load config into class
    #checks existence, loads default if 
    #not found
    def load_config(self):
        if len(list(self._config_collection.find({}))) == 0:
            try:
                with open(default_config_path, 'r') as cf_file:
                    #todo: add try/except 
                    self.config = json.load(cf_file)
                    self.push_config()
            except(FileNotFoundError):
                print("ERROR:default config file not found and no config exists within db")
        else:
            self.config = self._config_collection.find_one({}, {"_id":0})["ht_server_config"]

    #push config back to db
    def push_config(self):
        self._config_collection.update_one({}, {"$set":{"ht_server_config":self.config}})

    def save_config(self, filepath=default_config_path):
        conf = self._config_collection.find_one({}, {"_id":0})
        if conf != None:
            cur_config = conf
            with open(filepath, 'w+') as cf_file:
                json.dump(cur_config, cf_file, indent=4)

