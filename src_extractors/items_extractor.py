import pandas as pd
import csv
from .base import config
from src_backend.local_readers import Readers

def extract():
	flnames_jp = config['inputs']['jp']['items']
	flnames_en = config['inputs']['en']['items']
	fl_out = config['outputs']['items']
	
	def isvalid(ID: int, s: str) -> bool:
		return len(s) == len(s.encode()) and ID < 999
	
	print("Started extracting items")
	items_jp = pd.read_csv(flnames_jp['main'], sep=',', header=None, usecols=[0]).dropna().to_dict()[0]
	items_en = pd.read_csv(flnames_en['main'], sep='|', header=None, usecols=[0]).dropna().to_dict()[0]
	dcjp = pd.read_csv(flnames_jp['dropchara'], header=0, usecols=[0, 2], index_col=0).dropna()
	drop_chara_jp = dcjp[dcjp.index != -1].to_dict("index")
	sever_jp = pd.read_csv(flnames_jp['gib'], sep=',').dropna().to_dict()['SeverID']
	
	out = pd.read_csv(fl_out, sep='\t', index_col='ID').to_dict()['name']
	
	# update existing
	
	for i in out:
		if not isvalid(i, out[i]):
			try:
				out[i] = items_en[i]
			except KeyError:
				pass
	
	# append new
	
	for i in items_jp:
		try:
			out[i]
		except KeyError:
			try:
				out[i] = items_en[i]
			except KeyError:
				out[i] = items_jp[i]
	
	for i in drop_chara_jp:
		try:
			out[i]
		except KeyError:
			out[i] = Readers.getCat(drop_chara_jp[i]["charaID"], 0)
	
	out = dict(sorted(out.items()))
	
	with open(fl_out, encoding='utf-8', mode='w', newline='') as fl1:
		writer = csv.DictWriter(fl1, fieldnames=["ID", "name", "severID"], delimiter='\t')
		writer.writeheader()
		for row in out:
			try:
				writer.writerow({"ID": row, "name": out[row], "severID": sever_jp[row]})
			except KeyError:
				writer.writerow({"ID": row, "name": out[row], "severID": -1})
	print("Finished extracting items")
	
if __name__ == "__main__":
	extract()
