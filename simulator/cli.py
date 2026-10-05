from __future__ import annotations
import argparse,os,time
from datetime import datetime,timezone
from pathlib import Path
from .fleet import Fleet
from .transports import HttpTransport,AwsIotTransport

def main():
    p=argparse.ArgumentParser(description="QuakeMesh deterministic virtual-phone fleet")
    p.add_argument("--devices",type=int,default=25);p.add_argument("--scenario",choices=["isolated","same-cell","distributed","degraded"],default="distributed")
    p.add_argument("--center-lat",type=float,default=12.9716);p.add_argument("--center-lon",type=float,default=77.5946);p.add_argument("--seed",type=int,default=42)
    p.add_argument("--transport",choices=["http","mqtt"],default="http");p.add_argument("--base-url",default=os.getenv("QM_API_BASE_URL","http://127.0.0.1:8000"))
    p.add_argument("--api-key",default=os.getenv("QM_API_KEY"));p.add_argument("--iot-endpoint",default=os.getenv("QM_IOT_ENDPOINT"));p.add_argument("--cert-dir",default="artifacts/iot-devices");p.add_argument("--root-ca",default="artifacts/AmazonRootCA1.pem")
    p.add_argument("--trace",default=None)
    p.add_argument("--alert-wait-seconds",type=float,default=8.0,help="MQTT only: time to keep subscriptions open for cloud alerts after injection")
    a=p.parse_args()
    if a.devices<1: p.error("--devices must be >= 1")
    trace=a.trace or f"artifacts/traces/{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{a.scenario}.json"
    if a.transport=="http": transport=HttpTransport(a.base_url,a.api_key)
    else:
        if not a.iot_endpoint:p.error("--iot-endpoint or QM_IOT_ENDPOINT is required for mqtt")
        transport=AwsIotTransport(a.iot_endpoint,a.cert_dir,a.root_ca)
    fleet=Fleet(Fleet.around(a.devices,a.center_lat,a.center_lon),transport,a.seed,trace)
    alerts=0
    try:
        fleet.scenario(a.scenario)
        if a.transport=="mqtt" and a.alert_wait_seconds>0:
            time.sleep(a.alert_wait_seconds)
            alerts=fleet.collect_transport_alerts()
    finally:
        transport.close();fleet.flush_trace()
    errors=sum(1 for x in fleet.trace if x.get("error"));print(f"records={len(fleet.trace)} errors={errors} alerts_received={alerts} trace={trace}")

if __name__=="__main__":main()
