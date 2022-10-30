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

    def get_data_from_range(self, mac_addr, delta=12):
        #from_datetime will assume time is in UTC, adjust .now() so we don't get an extra 4 hours
        dummy_id = objectid.ObjectId.from_datetime(datetime.now(timezone.utc) - timedelta(hours=delta))
        print(datetime.now() - timedelta(hours=delta))
        measurements = self.measurements.find({"_id": {"$gte": dummy_id}, "MAC": mac_addr}, {"_id":0})
        
        data = [i for i in measurements]
        
        return data

    def get_db_size_str(self):
        size = int(self.db.command("collstats", "measurements")["size"])
        if size > 1000000000:
            dbsize = "{0} Gb".format(size/1000000)
        elif size > 1000000:
            dbsize = "{0} Mb".format(size/1000000)
        elif size > 1000:
            dbsize = "{0} kb".format(size/1000) 
        else:
            dbsize = "{0} b".format(size)

        return dbsize


presets = {"last_12":    {"disp":"Last 12 Hours", "delta": 12}, 
            "last_hour": {"disp":"Last Hour", "delta":1}, 
            "last_day":  {"disp":"Last Day", "delta":24}, 
            "last_week": {"disp":"Last Week", "delta":24*7}, 
            "last_month":{"disp":"Last Month", "delta":24*7*30}}


#class to standardize the config access
class configuration:
    MIN_REFRESH_RATE = 0
    MAX_REFRESH_RATE = 1000
    _db = None
    _config_collection = None
    config_dict = None
    presets = None

    def __init__(self, db):
        self._db = db
        self._config_collection = db.db['config']
        self.presets = presets
        self.config_dict = dict()
        self.load_config()

    def __getattr__(self, name):

        if name in self.config_dict.keys():
            return self.config_dict[str(name)]
        

    def __setattr__(self, __name: str, __value) -> None:   
        try:
            super().__setattr__(__name, __value)
        except AttributeError:
            if __name in self.config_dict.keys():
                    if __name == "m_sync_refresh_rate":
                        if __value <= self.MIN_REFRESH_RATE or __value > self.MAX_REFRESH_RATE:
                            return
                    self.config_dict[__name] = __value
      

    def __repr__(self) -> str:
        return json.dumps(self.config_dict, indent=4)

    def keys(self) -> list:
        return self.config_dict.keys()

    

    #load config into class
    #checks existence, loads default if 
    #not found
    def load_config(self):
        if self._config_collection.find_one({}, {"_id":0}) is None:
            try:
                with open(default_config_path, 'r') as cf_file:
                    #todo: add try/except 
                    self.config_dict = json.load(cf_file)
                    self.push_config()
            except(FileNotFoundError):
                print("ERROR:default config file not found and no config exists within db")
        else:
            self.config_dict = self._config_collection.find_one({}, {"_id":0})["ht_server_config"]
            if "devices" not in self.config_dict.keys():
                self.config_dict["devices"]  = list(self._db.db["devices"].find({}, {"_id":0, "measurements":0}))

    def set_and_push(self, key, value):
            self.config[key] = value
            self.push_config()

    def get_device(self, mac):
        for dev in self.config_dict["devices"]:
            if dev["MAC"] == mac:
                return dev
        return None

    def set_device_attr(self, mac, name, value):
        for dev in self.devices:
            if dev["MAC"] == mac:
                dev[name] = value
                #self._db.devices.update_one({"MAC":dev["MAC"]}, {"$set" : {name:value}}) #redundancy for now
                self.push_config()

    def get_cur_delta(self):
        return presets[self.data_period]["delta"]

    def rebuild_config(self):
        with open(default_config_path+".bak", 'r') as cf_file:
            self.config_dict = {}
            self.config_dict = json.load(cf_file)["ht_server_config"]
            print(json.dumps(self.config_dict, indent=4))
            self.push_config()

    #push config back to db
    def push_config(self):
        conf_id = self._config_collection.find_one({})["_id"]
        print("pushin")
        self._config_collection.update_one({"_id": conf_id}, {"$set":{"ht_server_config":self.config_dict}})

    def save_config(self, filepath=default_config_path):
        conf = self._config_collection.find_one({}, {"_id":0})
        if conf != None:
            cur_config = conf
            with open(filepath, 'w+') as cf_file:
                json.dump(cur_config, cf_file, indent=4)

