from pymongo import MongoClient
from bson import objectid
import json
import copy
import os
from datetime import datetime, timedelta

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
        
    def get_refresh_rate(self):
        refresh_rate = self.get_config()["m_sync_refresh_rate"]
        return int(refresh_rate)

    def get_data_from_range(self, mac_addr, start, end, reverse=True):
        #dev = self.devices.find_one({"MAC":mac_addr})
        dummy_id = objectid.ObjectId.from_datetime(datetime.now() - timedelta(hours=24))
        measurements = self.measurements.find({"_id": {"$gte": dummy_id}, "MAC": mac_addr}, {"_id":0})
        print(measurements)
        data = [i for i in measurements]
        print(data)
        return data

        # start_found = False
        # end_found = False 
        # if reverse:
        #     search_array = reversed(dev["measurements"])
        # else:
        #     search_array = dev["measurements"]
        # ret = []
        # last = None
        # for obj_id in search_array:
        #     mes = self.measurements.find_one({"_id":obj_id}, {"_id": 0}).copy()
        #     dtime = datetime.strptime(mes["date"] + " " + mes["time"], "%d/%m/%Y %H:%M:%S")
        #     if last is not None:
        #         last_time = datetime.strptime(last["date"] + " " + last["time"], "%d/%m/%Y %H:%M:%S")
        #     if reverse:
        #         if end_found:
        #             ret.append(mes)
        #             last = mes
        #         else:
        #             if dtime > end:
        #                 last = mes
        #             elif dtime < end and dtime > last_time:
        #                 ret.append(mes)
        #                 end_found = True

        #         if not start_found:
        #             if dtime > start:
        #                 last = mes
        #             elif dtime < start and dtime > last_time:
        #                 ret.append(mes)
        #                 break

        #     else:
        #         if start_found:
        #             ret.append(mes)
        #             last = mes
        #         else:
        #             if dtime < start:
        #                 last = mes
        #             elif dtime > start and dtime < last_time:
        #                 ret.append(mes)
        #                 start_found = True
                
        #         if not end_found:
        #             if dtime < end:
        #                 last = mes
        #             elif dtime > end and dtime < last_time:
        #                 ret.append(mes)
        #                 break

        # return ret

    def get_n_last_data(self, mac_addr, n):
        dev = self.devices.find_one({"MAC":mac_addr})
        ret = []
        n_found = 0
        for i in reversed(dev["measurements"]):
            if n_found == n:
                break
            ret.append(i)
            n_found += 1
        return ret


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
