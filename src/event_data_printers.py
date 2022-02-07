import datetime
import json
import time
import platform
import os

import flask_restful
import requests

from .event_data_fetchers import GatyaFetcher, StageFetcher, ItemFetcher, StageParsers
from .containers import Colourer
import asyncio
import aiohttp
import flask
from flask_restful import Resource
from flask_httpauth import HTTPBasicAuth

CASE = 0
LANG = 'en'
f = ['N']

with open("_config.json") as fl:
	config = json.load(fl)

"""TODO:
4 combos tsv
"""

auth = HTTPBasicAuth()
credentials = os.environ

hooks = json.loads(credentials.get("HOOKURL"))
LOGURL = credentials.get("LOGURL")

TIMED = credentials.get("TIMING") == 'True'
LOCAL = credentials.get("LOCAL") == 'True'
LOGGING = credentials.get("LOGGING") == 'True'


@auth.verify_password
def verify_password(username, password):
	if credentials["USER"] == username and credentials["PASS"] == password:
		return username
	elif credentials["SUPERUSER"] == username and credentials["SUPERPASS"] == password:
		return username

def fetch_test(lang: str, num: int) -> dict[str, str]:
	toret = {}
	for cat in ["Gatya", "Sale", "Item"]:
		text = ""
		with open(f"../tests/in/{lang}{num}{cat[0]}.tsv", encoding='utf-8') as fl0:
			rows = fl0.read().split('\n')
			for row in rows:
				if row.startswith('+ '):
					text += row[2:] + '\n'
		toret[cat] = text
	return toret

URLs = {"Gatya": "https://bc-seek.godfat.org/seek/%s/gatya.tsv",
        "Sale": "https://bc-seek.godfat.org/seek/%s/sale.tsv",
        "Item": "https://bc-seek.godfat.org/seek/%s/item.tsv"}

if platform.system() == "Windows":
	asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
	
async def fetch_all(ver: str, urls: dict[str, str] = URLs) -> dict[str, str]:
	toret = {}
	async with aiohttp.ClientSession() as session:
		for U in URLs:
			async with session.get(urls[U] % ver, headers={'Referer': 'https://bc.godfat.org/logs'}) as response:
				toret[U] = await response.text()
	
	return toret

def print_t(X: any) -> None:
	if TIMED:
		print(X)
		
class Funky(Resource):
	@auth.login_required
	def post(self) -> str:
		start = time.time()
		if TIMED: print_t(f"started at {start}")
		
		js = flask_restful.request.get_json()
		texts = js["diffs"]
		ver = "BC" + (js["version"][:2] if js.get("version") is not None else "??").upper()
		plain = js.get("plain") if js.get("plain") is not None else True

		clr = Colourer()
		if not plain:
			clr.enable()
		
		for key in texts:
			rows = texts[key].split("\n")
			toput = ""
			for row in rows:
				if row.startswith('+ '):
					toput += row[2:] + '\n'
			texts[key] = toput
		
		gf = GatyaFetcher(fls=f, coloured=clr)
		sf = StageFetcher(fls=f, coloured=clr)
		itf = ItemFetcher(fls=f, coloured=clr)
		
		gf.fetchRawData(texts["Gatya"])
		sf.fetchRawData(texts["Sale"])
		itf.fetchRawData(texts["Item"])
		
		if LOGGING == 'True':
			requests.post(LOGURL, {"content": "```\n"+str(js)+"\n```"})
		
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
		
		toprint: list[str] = [f"**{ver} EVENT DATA**\n"]
		toprint[0] += gf.printGatya()
		toprint[0] += sf.printStages()
		toprint[0] += itf.printItemData()
		toprint.append(sf.printFestivalData())
		
		for_export = {"gatya": gf.package(),
		              "stages": sf.package(),
		              "items": itf.package()}
		
		def unfuck_dates(obj):
			if isinstance(obj, datetime.datetime):
				return obj.isoformat()
			else:
				return str(obj)
		
		with open(config["outputs"]["eventdata"] + "gatya_final.txt", "w+", encoding='utf-8') as fl0:
			fl0.write("".join(toprint))
		with open(config["outputs"]["eventdata"] + "export.json", mode='w+') as fl0:
			json.dump(for_export, fl0, indent=2, default=unfuck_dates)
		if credentials.get("LOCAL") == "FALSE":
			if LOGGING == 'True':
				requests.post(LOGURL, {"attachments": [{"filename": config['outputs']['eventdata'] + "export.json"}]})
		
		print(f"over - {time.time() - start}")
		StageParsers.updateEventNames()
		# gf.exportGatya()
		# sf.exportStages()
		if auth.username() == credentials["SUPERUSER"]:
			X = js["destinations"]
			if X is None: X = '["test"]'
			if credentials.get("TESTING") == "True":
				X = '["test"]'
			destinations = json.loads(X)
			for dest in destinations:
				if dest in hooks:
					for i in toprint:
						if i == "":
							continue
						response = requests.post(hooks[dest], {"content": i})
						if not 200 <= response.status_code < 300:
							print("Webhook Write Failed: " + str(response.status_code) + ": " + response.text)
							return "Webhook Write Failed"
		return "".join(toprint)

app = flask.Flask(__name__)
api = flask_restful.Api(app)

api.add_resource(Funky, '/funky')
