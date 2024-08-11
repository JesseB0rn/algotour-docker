"""
Watches for changes in firestore collection, then processes sequentially
Also sanitizes coords
"""
from config import *
try:
  from local_config import *
except ImportError:
  pass

import json
import subprocess
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud.firestore_v1._helpers import GeoPoint
from sys import stderr

cred = credentials.Certificate(FB_PRIVATE_KEY)
firebase_admin.initialize_app(cred)
db = firestore.client()

class EModel:
    NAIVE = 0
    LAKES = 1
    ALL = 2


def calculate_path(startpoint: GeoPoint, endpoint: GeoPoint, model = EModel.ALL):
  cmd = ""
  match model:
    case EModel.LAKES:
      cmd=f"{QGS_PRC_PATH} run model:LeastCostCorridorWalk --distance_units=meters --area_units=m2 --ellipsoid=EPSG:7004 --startp='{startpoint.longitude},{startpoint.latitude} [EPSG:4326]' --endp='{endpoint.longitude},{endpoint.latitude} [EPSG:4326]' --points_crs='EPSG:4326' --risikokarte={MODELS['water']} --dem={DEM} --avy_cost_coeff=45 --steep_downhill=5 --downhill=2.5 --flat=0.25 --uphill=2.5 --steep_uphill=5 --outputpath={OUTPATH}out_$(uuidgen).geojson --json"
      # cmd=f"{QGS_PRC_PATH} run model:LeastCostCorridorWalk --distance_units=meters --area_units=m2 --ellipsoid=EPSG:7004 --startp='{startpoint.longitude},{startpoint.latitude} [EPSG:4326]' --endp='{endpoint.longitude},{endpoint.latitude} [EPSG:4326]' --points_crs='EPSG:4326' --risikokarte={RISKMAP_LAKES} --dem={DEM} --avy_cost_coeff=0.4 --steep_downhill=5 --downhill=0.0025 --flat=0.00025 --uphill=0.0025 --steep_uphill=5 --outputpath=/root/routes/out_$(uuidgen).geojson --json"
    case EModel.NAIVE:
      # cmd=f"{QGS_PRC_PATH} run model:LeastCostCorridorWalk --distance_units=meters --area_units=m2 --ellipsoid=EPSG:7004 --startp='{startpoint.longitude},{startpoint.latitude} [EPSG:4326]' --endp='{endpoint.longitude},{endpoint.latitude} [EPSG:4326]' --points_crs='EPSG:4326' --risikokarte={RISKMAP_BASE} --dem={DEM} --avy_cost_coeff=0.4 --steep_downhill=5 --downhill=0.0025 --flat=0.00025 --uphill=0.0025 --steep_uphill=5 --outputpath=/root/routes/out_$(uuidgen).geojson --json"
      cmd=f"{QGS_PRC_PATH} run model:LeastCostCorridorWalk --distance_units=meters --area_units=m2 --ellipsoid=EPSG:7004 --startp='{startpoint.longitude},{startpoint.latitude} [EPSG:4326]' --endp='{endpoint.longitude},{endpoint.latitude} [EPSG:4326]' --points_crs='EPSG:4326' --risikokarte={MODELS['base']} --dem={DEM} --avy_cost_coeff=45 --steep_downhill=5 --downhill=2.5 --flat=0.25 --uphill=2.5 --steep_uphill=5 --outputpath={OUTPATH}out_$(uuidgen).geojson --json"
    case _:
      # cmd=f"{QGS_PRC_PATH} run model:LeastCostCorridorWalk --distance_units=meters --area_units=m2 --ellipsoid=EPSG:7004 --startp='{startpoint.longitude},{startpoint.latitude} [EPSG:4326]' --endp='{endpoint.longitude},{endpoint.latitude} [EPSG:4326]' --points_crs='EPSG:4326' --risikokarte={RISKMAP_ALL} --dem={DEM} --avy_cost_coeff=0.4 --steep_downhill=5 --downhill=0.0025 --flat=0.00025 --uphill=0.0025 --steep_uphill=5 --outputpath=/root/routes/out_$(uuidgen).geojson --json"
      cmd=f"{QGS_PRC_PATH} run model:LeastCostCorridorWalk --distance_units=meters --area_units=m2 --ellipsoid=EPSG:7004 --startp='{startpoint.longitude},{startpoint.latitude} [EPSG:4326]' --endp='{endpoint.longitude},{endpoint.latitude} [EPSG:4326]' --points_crs='EPSG:4326' --risikokarte={MODELS['bridge']} --dem={DEM} --avy_cost_coeff=45 --steep_downhill=5 --downhill=2.5 --flat=0.25 --uphill=2.5 --steep_uphill=5 --outputpath={OUTPATH}out_$(uuidgen).geojson --json"
  



  print("running:", cmd)

  result = subprocess.check_output(cmd, shell=True)
  print(outpath := json.loads(result)['results']['outputpath'])
  
  return outpath

# Function to process new document
def process_new_document(doc_data, ref):
    print("Processing new document:")
    ref.update({
          'state': 'processing'
      })
    print(doc_data)
    model = EModel.NAIVE 
    model = EModel.ALL if doc_data['modelversion'] == "lake+street" else model
    model = EModel.LAKES if doc_data['modelversion'] == "lake" else model
    print(model)
    outpath = calculate_path(doc_data['startpoint'], doc_data['endpoint'], model)

    o = json.load(open(outpath))
    print(o)
    with open(outpath) as o:
      print('writing ref')
      ref.update({
          'route': o.read(),
          'state': 'processed'
      })
    print('request closed')

# Callback function to handle changes
def on_snapshot(col_snapshot, changes, read_time):
    print(f"Snapshot received at {read_time}")
    for change in changes:
        if change.type.name == 'ADDED':
            print(f"[Firestore] New document: {change.document.id}")
            # Get the new document's data
            doc_data = change.document.to_dict()
            # Call the processing function with the new document's data
            
            nd = process_new_document(doc_data, change.document.reference)
            print("ERROR processing doc", change.document.reference)

        elif change.type.name == 'MODIFIED':
            print(f"[Firestore] Modified document: {change.document.id}")
        elif change.type.name == 'REMOVED':
            print(f"[Firestore] Removed document: {change.document.id}")

# Reference to the collection
collection_ref = db.collection('tours')

# Watch the collection
col_query_watch = collection_ref.where(filter=FieldFilter("state", '==', 'waiting')).on_snapshot(on_snapshot)

# Keep the application running to listen for changes
import time
while True:
    time.sleep(1)
