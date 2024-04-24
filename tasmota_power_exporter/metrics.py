import requests
import sys
import signal
from os import getenv
from time import sleep
from prometheus_client.core import GaugeMetricFamily, REGISTRY, CounterMetricFamily
from prometheus_client import start_http_server
from urllib.parse import urlparse, urlunparse
import string
import argparse

parser  = argparse.ArgumentParser()

parser.add_argument(
    '--device',
    action='append',
    help='Can be used multiple times. DEVICE has format of "<ip>:<port> [user password]"',
    nargs='+',
    required=True
)

args = parser.parse_args()

def argToConf(arg) -> dict:
    if not isinstance(arg, list):
        raise RuntimeError("Argument is not a list")
    
    if len(arg) == 1:
        return (arg[0], None, None)
    elif len(arg) == 3:
        return (arg[0], arg[1], arg[2])
    
    raise RuntimeError("Wrong number of items for arg")

devices = [argToConf(conf) for conf in args.device]

printable = set(string.printable)
ext_printable = set(string.printable + '°')

class TasmotaCollector(object):
    def __init__(self):
        self.devices = devices

    def collect(self):
        for device in devices:
            response = self.fetch(device[0], device[1], device[2])

            if not response:
                continue

            for key in response:
                [value, unit] = response[key]
                metric_name = "tasmota_" + key.lower().replace(" ", "_") 
                metric = value.split()[0]

                extra_labels = ['device']
                extra_metrics = [device[0]]

                if unit:
                    extra_labels.append('unit')
                    extra_metrics.append(unit)

                if "today" in metric_name or "yesterday" in metric_name or "total" in metric_name:
                    r = CounterMetricFamily(metric_name, key, labels=extra_labels)
                else:
                    r = GaugeMetricFamily(metric_name, key, labels=extra_labels)
                r.add_metric(extra_metrics, metric)
                yield r

    def fetch(self, url: str, username: str | None = None, password: str | None = None, use_ssl: bool = False) -> dict | None:
        try:
            url = f'{"https" if use_ssl else "http"}://{url}/?m=1'

            session = requests.Session()
            
            if username and password:
                session.auth = (username, password)

            response = session.get(url)
            response.raise_for_status()

            values = {}

            string_values = str(response.text).split("{s}")
            for i in range(1,len(string_values)):
                try:
                    label = string_values[i].split("{m}")[0]
                    value = string_values[i].split("{m}")[1].split("{e}")[0]
                    if "<td" in value:
                        value = value.replace("</td><td style='text-align:left'>", "")
                        value = value.replace("</td><td>&nbsp;</td><td>", "")

                    label = label.strip()

                    value = (''.join(filter(lambda x: x in ext_printable, value)))

                    value = value.strip()

                    unit = None

                    if len(value.split()) > 1:
                        unit = value.split()[1]
                    elif 'Power Factor' in label:
                        unit = ''

                    values[label] = (value, unit)
                except IndexError:
                    continue
            return values
        except Exception as e:
            print(e)
            return {}

def signal_handler(signal, frame):
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def run_exporter():
    port = getenv('EXPORTER_PORT', 8000)

    start_http_server(int(port))
    REGISTRY.register(TasmotaCollector())

    while(True):
        sleep(1)
    

if __name__ == '__main__':
    run_exporter()
