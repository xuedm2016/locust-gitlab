# -*- coding:utf-8 -*-
from influxdb import InfluxDBClient
import pymysql
import os

def connect_influx():
    influxdb_host = os.environ.get('INFLUXDB_HOST', '172.18.143.48')
    influxdb_user = os.environ.get('INFLUXDB_USER', 'root')
    influxdb_password = os.environ.get('INFLUXDB_PASSWORD', 'root')
    influxdb_dbname = os.environ.get('INFLUXDB_DBNAME','statsdb')
    client = InfluxDBClient(influxdb_host, 8086, influxdb_user, influxdb_password, influxdb_dbname)
    print ("INFLUXDB HOST is: %s \n" % influxdb_host)
    return client

def connect_mysql():
    mysql_host = os.environ.get('MYSQL_HOST', '36.111.164.243')
    mysql_user = os.environ.get('MYSQL_USER', 'dtpuser')
    mysql_password = os.environ.get('MYSQL_PASSWORD', 'NewPassw0rd!')
    mysql_dbname = os.environ.get('MYSQL_DBNAME', 'dtp2')
    conn = pymysql.connect(host=mysql_host, port=3306, user=mysql_user, passwd=mysql_password, db=mysql_dbname, charset='utf8')
    return conn

