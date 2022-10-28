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
