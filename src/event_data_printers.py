import datetime
import json
import time
import platform
import os
import io
import ast

import flask_restful
import requests

from src_backend.event_data_fetchers import GatyaFetcher, StageFetcher, ItemFetcher
from src_backend.containers import Colourer
import asyncio
import aiohttp
import flask
from flask_restful import Resource
from flask_httpauth import HTTPBasicAuth

with open("_config.json") as fl:
	config = json.load(fl)

"""TODO:
4 combos tsv
"""

auth = HTTPBasicAuth()
credentials = os.environ
if credentials is None:
	credentials = {}

hooks = json.loads(credentials.get("HOOKURL", "{}"))
LOGURL = credentials.get("LOGURL")

TIMED = credentials.get("TIMING") == 'True'
LOCAL = credentials.get("LOCAL") == 'True'
LOGGING = credentials.get("LOGGING") == 'True'
TESTING = credentials.get("TESTING") == 'True'

@auth.verify_password
def verify_password(username, password):
	if credentials["USER"] == username and credentials["PASS"] == password:
		return username
	elif credentials["SUPERUSER"] == username and credentials["SUPERPASS"] == password:
		return username

# region fetching from godfat
URLs = {"Gatya": "https://bc-seek.godfat.org/seek/%s/gatya.tsv",
        "Sale": "https://bc-seek.godfat.org/seek/%s/sale.tsv",
        "Item": "https://bc-seek.godfat.org/seek/%s/item.tsv"}

if platform.system() == "Windows":
	asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def fetch_all(ver: str, urls: dict[str, str] = URLs) -> dict[str, str]:
	toret = {}
	async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(verify_ssl=False)) as session:
		for U in URLs:
			async with session.get(urls[U] % ver, headers={'Referer': 'https://bc.godfat.org/logs'}) as response:
				toret[U] = await response.text()
	
	return toret

# endregion

def print_t(X: any) -> None:
	if TIMED:
		print(X)

def process(js):
	start = time.time()
	print_t(f"started at {start}")
	texts = js["diffs"]
	ver = "BC" + (js["version"][:2] if js.get("version") is not None else "??").upper()
	if ver not in ["BCEN", "BCJP"]:
		return "sorry we only take en/jp here"
	plain = js.get("plain") if js.get("plain") is not None else True
	
	clr = Colourer()
	if not plain:
		clr.enable()
	
	dummy = js.copy()
	dummy["diffs"] = {}
	for key in texts:
		rows = texts[key].split("\n")
		toput = ""
		tonotput = ""
		for row in rows:
			if row.startswith('- '):
				tonotput += row[2:] + '\n'
			elif row.startswith('+ '):
				toput += row[2:] + '\n'
			else:
				toput += row + '\n'
		texts[key] = toput
		dummy["diffs"][key] = tonotput
	
	# sends a query to process the - rows
	dummy["destinations"] = ["test"]
	
	FL = ['N'] if js.get("fetch", False) else []
	# process query
	gf = GatyaFetcher(fls=FL, coloured=clr)
	sf = StageFetcher(fls=FL, coloured=clr)
	itf = ItemFetcher(fls=FL, coloured=clr)
	
	if js.get("fetch", False):
		texts = asyncio.run(fetch_all(js["version"][:2].lower()))
		
	gf.fetchRawData(texts["Gatya"])
	sf.fetchRawData(texts["Sale"])
	itf.fetchRawData(texts["Item"])
	
	if LOGGING:
		test = "test"
		try:
			test = ast.literal_eval(f'"{str(js)}"')
			files = {"input.json": io.StringIO(test)}
			requests.post(LOGURL, files=files)
		except:
			print("uh-oh")
			
	print_t(f"reading raw gatya - {time.time() - start}")
	
	gf.readRawData()
	
	print_t(f"reading raw stages - {time.time() - start}")
	sf.readRawData(storeRejects=True)
	print_t(f"reading raw items - {time.time() - start}")
	itf.readRawData()
	
	print_t(f"merging items and stages - {time.time() - start}")
	sd0 = sf.refinedStages
	sd1 = itf.refinedData
	
	sd0.extend(sd1)
	
	print_t(f"grouping stages - {time.time() - start}")
	
	sf.finalStages, sf.festivals, sf.sales, sf.missions = sf.groupData(sf.refinedStages.copy())
	gf.refinedGatya = gf.groupData(gf.refinedGatya)[0]
	itf.finalItems = itf.groupData(itf.finalItems)[0]
	sf.sortAll()
	
	print_t(f"printing stuff - {time.time() - start}")
	
	# output query
	toprint: list[str] = [f"**{ver} EVENT DATA**\n"]
	toprint[0] += gf.printGatya()
	toprint.extend(sf.printStages())
	toprint.append(itf.printItemData())
	toprint.append(sf.printFestivalData())
	
	for_export = {"gatya": gf.package(),
	              "stages": sf.package(),
	              "items": itf.package()}
	
	def unfuck_dates(obj):
		if isinstance(obj, datetime.datetime):
			return obj.isoformat()
		elif isinstance(obj, Colourer):
			return obj.ENABLED
		else:
			return str(obj)
	
	with open(config["outputs"]["eventdata"] + "output.txt", "w+", encoding='utf-8') as fl0:
		fl0.write("".join(toprint))
	with open(config["outputs"]["eventdata"] + "export.json", mode='w+') as fl0:
		json.dump(for_export, fl0, indent=2, default=unfuck_dates)
	
	print(f"over - {time.time() - start}")
	# StageParsers.updateEventNames()
	return dummy, toprint

class Funky(Resource):
	@auth.login_required
	def post(self) -> str:
		# read query
		js = flask_restful.request.get_json()
		ver = "BC" + (js["version"][:2] if js.get("version") is not None else "??").upper()
		if ver not in ["BCEN", "BCJP"]:
			return ("unsupported version")
		dummy, toprint = process(js)
		
		if not LOCAL:
			if LOGGING:
				files = {"file1": open(config["outputs"]["eventdata"] + "export.json", mode="r", encoding='utf-8')}
				requests.post(LOGURL, files=files)
				
				files = {"file2": open(config["outputs"]["eventdata"] + "output.txt", mode="r", encoding='utf-8')}
				requests.post(LOGURL, files=files)
		
		if auth.username() == credentials["SUPERUSER"] and len(toprint[0]) + len(toprint[1]) > 30:
			destinations = js["destinations"]
			if destinations is None or TESTING:
				destinations = ["test"]
			
			for dest in destinations:
				if dest in hooks:
					for i in toprint:
						if i == "":
							continue
						requests.post(hooks[dest], {"content": i})
			
			if "rbc" in destinations:
				files = {"file1": open(config["outputs"]["eventdata"] + "output.txt", mode="r", encoding='utf-8')}
				requests.post(hooks["rbc"], files=files)
			
			if "fandom" in destinations:
				if ver == "BCEN":
					role = 647882379184308254
				else:
					role = 654577263605710850
				if len(toprint[0]) > 200:
					response = requests.post(hooks["fandom"], {"content": f"pinging <@&{role}>"})
					requests.post(hooks["test"], {"content": str(response.__dict__)})
				requests.post(hooks["test"], {"content": len(toprint[0])})
			
			tosend = process(dummy)[1][0]
			files = {"removed_stuff.txt": io.StringIO(tosend)}
			requests.post(hooks["test"], files=files)
		
		# requests.post(hooks["test"], {"content": f"pinging <@&837036121628213249>"})
		return "".join(toprint)

app = flask.Flask(__name__)
api = flask_restful.Api(app)

api.add_resource(Funky, '/funky')
