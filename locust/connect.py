# -*- coding:utf-8 -*-
from influxdb import InfluxDBClient
import pymysql

def connect_influx():
    client = InfluxDBClient('192.168.0.113', 8086, 'root', '', 'statsdb')
    return client

def connect_mysql():
    conn = pymysql.connect(host='127.0.0.1', port=3306, user='root', passwd='mysql', db='statsdb', charset='utf8')
    return conn

