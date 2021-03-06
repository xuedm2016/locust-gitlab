# encoding: utf-8

import csv
import json
import os.path
import datetime
import math
from time import time
from itertools import chain
from collections import defaultdict
from six.moves import StringIO, xrange
import six

from gevent import wsgi
from flask import Flask, make_response, request, render_template

from . import runners
from .cache import memoize
from .runners import MasterLocustRunner
from locust.stats import median_from_dict
from locust import __version__ as version

import logging
import connect
logger = logging.getLogger(__name__)

DEFAULT_CACHE_TIME = 2.0

app = Flask(__name__)
app.debug = True
app.root_path = os.path.dirname(os.path.abspath(__file__))


@app.route('/')
def index():
    is_distributed = isinstance(runners.locust_runner, MasterLocustRunner)
    if is_distributed:
        slave_count = runners.locust_runner.slave_count
    else:
        slave_count = 0

    if runners.locust_runner.host:
        host = runners.locust_runner.host
    elif len(runners.locust_runner.locust_classes) > 0:
        host = runners.locust_runner.locust_classes[0].host
    else:
        host = None
    
    return render_template("index.html",
        state=runners.locust_runner.state,
        is_distributed=is_distributed,
        slave_count=slave_count,
        user_count=runners.locust_runner.user_count,
        version=version,
        host=host
    )

@app.route('/swarm', methods=["POST"])
def swarm():
    assert request.method == "POST"

    locust_count = int(request.form["locust_count"])
    hatch_rate = float(request.form["hatch_rate"])
    #update code to accept the parameter of "report_id" to write mysql db after testing is done.
    global report_id
    report_id = int(request.form["report_id"])
    runners.locust_runner.start_hatching(locust_count, hatch_rate)
    response = make_response(json.dumps({'success':True, 'message': 'Swarming started'}))
    response.headers["Content-type"] = "application/json"
    return response

@app.route('/stop')
def stop():
    runners.locust_runner.stop()
    response = make_response(json.dumps({'success':True, 'message': 'Test stopped'}))
    response.headers["Content-type"] = "application/json"
    return response

@app.route("/stats/reset")
def reset_stats():
    runners.locust_runner.stats.reset_all()
    return "ok"
    
@app.route("/stats/requests/csv")
def request_stats_csv():
    rows = [
        ",".join([
            '"Method"',
            '"Name"',
            '"# requests"',
            '"# failures"',
            '"Median response time"',
            '"Average response time"',
            '"Min response time"', 
            '"Max response time"',
            '"Average Content Size"',
            '"Requests/s"',
        ])
    ]
    
    for s in chain(_sort_stats(runners.locust_runner.request_stats), [runners.locust_runner.stats.aggregated_stats("Total", full_request_history=True)]):
        rows.append('"%s","%s",%i,%i,%i,%i,%i,%i,%i,%.2f' % (
            s.method,
            s.name,
            s.num_requests,
            s.num_failures,
            s.median_response_time,
            s.avg_response_time,
            s.min_response_time or 0,
            s.max_response_time,
            s.avg_content_length,
            s.total_rps,
        ))

    response = make_response("\n".join(rows))
    file_name = "requests_{0}.csv".format(time())
    disposition = "attachment;filename={0}".format(file_name)
    response.headers["Content-type"] = "text/csv"
    response.headers["Content-disposition"] = disposition
    return response

@app.route("/stats/distribution/csv")
def distribution_stats_csv():
    rows = [",".join((
        '"Name"',
        '"# requests"',
        '"50%"',
        '"66%"',
        '"75%"',
        '"80%"',
        '"90%"',
        '"95%"',
        '"98%"',
        '"99%"',
        '"100%"',
    ))]
    for s in chain(_sort_stats(runners.locust_runner.request_stats), [runners.locust_runner.stats.aggregated_stats("Total", full_request_history=True)]):
        if s.num_requests:
            rows.append(s.percentile(tpl='"%s",%i,%i,%i,%i,%i,%i,%i,%i,%i,%i'))
        else:
            rows.append('"%s",0,"N/A","N/A","N/A","N/A","N/A","N/A","N/A","N/A","N/A"' % s.name)

    response = make_response("\n".join(rows))
    file_name = "distribution_{0}.csv".format(time())
    disposition = "attachment;filename={0}".format(file_name)
    response.headers["Content-type"] = "text/csv"
    response.headers["Content-disposition"] = disposition
    return response

@app.route('/stats/requests')
@memoize(timeout=DEFAULT_CACHE_TIME, dynamic_timeout=True)
def request_stats(g_state=[''],last_user_count=[None],count_list=[None]):
    stats = []
    for s in chain(_sort_stats(runners.locust_runner.request_stats), [runners.locust_runner.stats.aggregated_stats("Total")]):
        stats.append({
            "method": s.method,
            "name": s.name,
            "num_requests": s.num_requests,
            "num_failures": s.num_failures,
            "avg_response_time": s.avg_response_time,
            "min_response_time": s.min_response_time or 0,
            "max_response_time": s.max_response_time,
            "current_rps": s.current_rps,
            "median_response_time": s.median_response_time,
            "avg_content_length": s.avg_content_length,
        })

    errors = [e.to_dict() for e in six.itervalues(runners.locust_runner.errors)]

    # Truncate the total number of stats and errors displayed since a large number of rows will cause the app
    # to render extremely slowly. Aggregate stats should be preserved.
    report = {"stats": stats[:500], "errors": errors[:500]}

    if stats:
        report["total_rps"] = stats[len(stats)-1]["current_rps"]
        report["fail_ratio"] = runners.locust_runner.stats.aggregated_stats("Total").fail_ratio
        
        # since generating a total response times dict with all response times from all
        # urls is slow, we make a new total response time dict which will consist of one
        # entry per url with the median response time as key and the number of requests as
        # value
        response_times = defaultdict(int) # used for calculating total median
        for i in xrange(len(stats)-1):
            response_times[stats[i]["median_response_time"]] += stats[i]["num_requests"]
        
        # calculate total median
        stats[len(stats)-1]["median_response_time"] = median_from_dict(stats[len(stats)-1]["num_requests"], response_times)
    
    is_distributed = isinstance(runners.locust_runner, MasterLocustRunner)
    if is_distributed:
        report["slave_count"] = runners.locust_runner.slave_count
    
    report["state"] = runners.locust_runner.state
    report["user_count"] = runners.locust_runner.user_count
   # start write test data to influxdb and mysqldb.
    task_id = os.environ.get('TASK_ID')
   # user_id = os.environ.get('USER_ID')
   # area_id = os.environ.get('AREA_ID')
    client = connect.connect_influx()
    write_time = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    if report["state"] == "running" or report["state"] == "hatching" or (report["state"] == "stopped" and report['state']!=g_state[0]):
        for i in report['stats']:
            json_body = [
                {
                    "measurement": "stats_1",
                    "tags": {
                        "name": "%s" % i['name'],
                        "method": "%s" % i['method'],
                        "report_id":"%s" % report_id,
                        "task_id":"%s" % task_id
                    },
                    "time": "%s" % write_time,

                    "fields": {
                        "median_response_time": "%s" % i['median_response_time'],
                        "min_response_time": "%s" % i['min_response_time'],
                        "current_rps": "%s" % i['current_rps'],

                        "num_failures": "%d" % i['num_failures'],
                        "max_response_time": "%s" % i['max_response_time'],
                        "avg_content_length": "%d" % i['avg_content_length'],
                        "avg_response_time": "%s" % i['avg_response_time'],

                        "num_requests": "%d" % i['num_requests']
                    }
                }
            ]
            client.write_points(json_body)

        json_body_stated = [
            {
                "measurement": "stated_1",
                "tags": {
                    "report_id":"%s" % report_id,
                    "task_id":"%s" % task_id
                },

                "time": "%s" % write_time,

                "fields": {
                    "state": "%s" % report['state'],
                    "total_rps": "%s" % report['total_rps'],
                    "fail_ratio": "%s" % report['fail_ratio'],
                    "user_count": "%s" % (report['user_count'] if (report["state"] == "running" or report["state"] == "hatching") else last_user_count[0])
                }
            }
        ]

        client.write_points(json_body_stated)
    if report['state'] == 'stopped' and report['state'] != g_state[0]:
        B, C, D = round(report['total_rps'], 2), round(report['fail_ratio'], 4) * 100, max(count_list)
        conn = connect.connect_mysql()
        try:
            with conn.cursor() as cursor:
                sql_report = 'UPDATE dtp_report set total_rps=%s,total_fail_ratio=%s,simulate_users=%s WHERE task_id=%s and id=%s'
                sql_result = 'INSERT INTO dtp_result(url,total_average_rt,total_requests,total_failed,report_id) values(%s,%s,%s,%s,%s)'
                cursor.execute(sql_report, (B, C, D,task_id,report_id))

                for i in report['stats']:
                    cursor.execute(sql_result, (
                        i['name'], i['avg_response_time'], i['num_requests'], i['num_failures'],report_id))
            conn.commit()
        finally:
            conn.close()

    g_state[0] = report["state"]
    last_user_count[0] = report["user_count"]
    count_list.append(int(report["user_count"]))
    if len(count_list)>10:
        count_list.pop(0)
    return json.dumps(report)

@app.route("/exceptions")
def exceptions():
    response = make_response(json.dumps({
        'exceptions': [
            {
                "count": row["count"], 
                "msg": row["msg"], 
                "traceback": row["traceback"], 
                "nodes" : ", ".join(row["nodes"])
            } for row in six.itervalues(runners.locust_runner.exceptions)
        ]
    }))
    response.headers["Content-type"] = "application/json"
    return response

@app.route("/exceptions/csv")
def exceptions_csv():
    data = StringIO()
    writer = csv.writer(data)
    writer.writerow(["Count", "Message", "Traceback", "Nodes"])
    for exc in six.itervalues(runners.locust_runner.exceptions):
        nodes = ", ".join(exc["nodes"])
        writer.writerow([exc["count"], exc["msg"], exc["traceback"], nodes])
    
    data.seek(0)
    response = make_response(data.read())
    file_name = "exceptions_{0}.csv".format(time())
    disposition = "attachment;filename={0}".format(file_name)
    response.headers["Content-type"] = "text/csv"
    response.headers["Content-disposition"] = disposition
    return response

def start(locust, options):
    wsgi.WSGIServer((options.web_host, options.port), app, log=None).serve_forever()

def _sort_stats(stats):
    return [stats[key] for key in sorted(six.iterkeys(stats))]
