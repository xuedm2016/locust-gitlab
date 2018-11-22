# -*- coding:utf-8 -*-
from influxdb import InfluxDBClient
import pymysql
import os

def connect_influx():
    influxdb_host = os.environ.get('INFLUXDB_HOST', '172.18.143.20')
    influxdb_user = os.environ.get('INFLUXDB_USER', 'root')
    influxdb_password = os.environ.get('INFLUXDB_PASSWORD', '')
    influxdb_dbname = os.environ.get('INFLUXDB_DBNAME','statsdb')
    client = InfluxDBClient(influxdb_host, 8086, influxdb_user, influxdb_password, influxdb_dbname)
    print ("INFLUXDB HOST is: %s \n" % influxdb_host)
    return client

def connect_mysql():
    mysql_host = os.environ.get('MYSQL_HOST', '172.18.143.49')
    mysql_user = os.environ.get('MYSQL_USER', 'root')
    mysql_password = os.environ.get('MYSQL_PASSWORD', 'NewPassw0rd!')
    mysql_dbname = os.environ.get('MYSQL_DBNAME', 'statsdb')
    conn = pymysql.connect(host=mysql_host, port=3306, user=mysql_user, passwd=mysql_password, db=mysql_dbname, charset='utf8')
    return conn

