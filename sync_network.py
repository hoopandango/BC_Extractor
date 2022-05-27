import asyncio
import json
import pandas as pd

from csv import DictReader, DictWriter
from src_backend.z_downloaders import Downloaders
from src_backend.local_readers import Readers

async def scan(ID):
	return Readers.getMap(ID)

async def update_stages():
	for prefix in Downloaders.prefixes.keys():
		base = 1000*prefix
		for offset in range(0, 1000, 10):
			print(f"Scanning from {base+offset}")
			responses = await asyncio.gather(*[scan(base+offset+x) for x in range(10)])
			if responses == ["Unknown"]*10:
				break

def sort_file():
	with open('_config.json') as fl:
		config = json.load(fl)
	
	temp: pd.DataFrame = pd.read_csv(config["outputs"]["stages"], delimiter='\t')
	temp = temp.sort_values(by="ID")
	temp.to_csv(config["outputs"]["stages"], sep='\t', index=False)

if __name__ == "__main__":
	# asyncio.run(update_stages())
	sort_file()
