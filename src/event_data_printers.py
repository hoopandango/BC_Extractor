import datetime
import json
import time
import platform
import os

import flask_restful
import requests

from .event_data_fetchers import GatyaFetcher, StageFetcher, ItemFetcher, StageParsers
import asyncio
import aiohttp
import flask
from flask_restful import Resource
from flask_httpauth import HTTPBasicAuth

CASE = 0
LANG = 'jp'
f = ['N']

with open("_config.json") as fl:
	config = json.load(fl)

"""TODO:
4 combos tsv
10  all barons are grouped together
"""

auth = HTTPBasicAuth()

credentials = os.environ

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
					text+= row[2:]+'\n'
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

class Funky(Resource):
	@auth.login_required
	def post(self) -> str:
		start = time.time()
		# print(f"started at {start}")
		gf = GatyaFetcher(fls=f)
		sf = StageFetcher(fls=f)
		itf = ItemFetcher(fls=f)

		if CASE <= 0:
			js = flask_restful.request.get_json()
			texts = js["diffs"]
			ver = "BC"+(js["version"][:2]).upper()
			for key in texts:
				rows = texts[key].split("\n")
				toput = ""
				for row in rows:
					if row.startswith('+ '):
						toput += row[2:]+'\n'
				texts[key] = toput
		else:
			ver = ""
			texts = fetch_test(LANG, CASE)
		print(f"got at {time.time() - start}")

		gf.fetchRawData(texts["Gatya"])
		sf.fetchRawData(texts["Sale"])
		itf.fetchRawData(texts["Item"])

		# print(f"reading raw gatya - {time.time() - start}")

		gf.readRawData()

		# print(f"reading raw stages - {time.time() - start}")
		sf.readRawData(storeRejects=True)
		# print(f"reading raw items - {time.time() - start}")
		itf.readRawData()

		# print(f"merging items and stages - {time.time() - start}")
		sd0 = sf.refinedStages
		sd1 = itf.refinedData

		sd0.extend(sd1)

		# print(f"grouping stages - {time.time() - start}")
		sf.finalStages, sf.festivals, sf.sales, sf.missions = sf.groupData(sf.refinedStages.copy())
		gf.refinedGatya = gf.groupData(gf.refinedGatya)[0]
		itf.finalItems = gf.groupData(itf.finalItems)[0]
		sf.sortAll()
		# print(f"printing stuff - {time.time() - start}")

		toprint = ver+" EVENT DATA\n"
		toprint += gf.printGatya()
		toprint += sf.printStages()
		toprint += itf.printItemData()
		print(sf.printFestivalData())
		toprint += sf.printFestivalData() if sf.printFestivalData() else ""

		with open(config["outputs"]["eventdata"]+"gatya_final.txt", "w", encoding='utf-8') as fl0:
			fl0.write(toprint)

		# print(toprint)

		for_export = {"gatya": gf.package(),
									"stages": sf.package(),
									"items": itf.package()}

		def unfuck_dates(obj):
			if isinstance(obj, datetime.datetime):
				return obj.isoformat()
			else:
				return str(obj)

		with open(config["outputs"]["eventdata"]+"export.json", mode='w') as fl0:
			json.dump(for_export, fl0, indent=2, default=unfuck_dates)

		print(f"over - {time.time() - start}")
		StageParsers.updateEventNames()
		# gf.exportGatya()
		# sf.exportStages()
		if auth.username() == credentials["SUPERUSER"]:
			requests.post(credentials["HOOKURL"], {"content": toprint})
		return toprint

app = flask.Flask(__name__)
api = flask_restful.Api(app)

api.add_resource(Funky, '/funky')
