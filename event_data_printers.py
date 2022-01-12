import time

from event_data_fetchers import GatyaFetcher, StageFetcher, ItemFetcher, StageParsers
import asyncio
import aiohttp

CASE = 1

"""TODO:
1 gatya event grouping
4 combos tsv
5 better gatya "new" uber checking
7 more test cases
8 meow meow day grouping
9 proper text for rare ticket drops / updates / etc.
10  proper exporting
12 modularise everything
"""

def fetch_test(lang: str, num: int) -> dict[str, str]:
	toret = {}
	for cat in ["Gatya", "Sale", "Item"]:
		text = ""
		with open(f"tests/in/{lang}{num}{cat[0]}.tsv") as fl:
			rows = fl.read().split('\n')
			for row in rows:
				if row.startswith('+ '):
					text+= row[2:]+'\n'
		toret[cat] = text
	return toret

asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
async def fetch_all(ver: str) -> dict[str, str]:
	toret = {}
	URLs = {"Gatya": "https://bc-seek.godfat.org/seek/%s/gatya.tsv",
	        "Sale": "https://bc-seek.godfat.org/seek/%s/sale.tsv",
	        "Item": "https://bc-seek.godfat.org/seek/%s/item.tsv"}
	async with aiohttp.ClientSession() as session:
		for U in URLs:
			async with session.get(URLs[U] % ver, headers={'Referer': 'https://bc.godfat.org/logs'}) as response:
				toret[U] = await response.text()
	
	return toret

start = time.time()
# print(f"started at {start}")
gf = GatyaFetcher(fls=['N'])
sf = StageFetcher(fls=['N'])
itf = ItemFetcher(fls=['N'])

# texts = asyncio.run(fetch_all(gf.ver))
texts = fetch_test('en', CASE)
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
sf.finalStages, sf.sales, sf.missions = sf.groupData(sf.refinedStages)
sf.sortAll()
# print(f"printing stuff - {time.time() - start}")

gf.printGatya()
sf.printStages()
itf.printItemData()
sf.printFestivalData()

print(f"over - {time.time() - start}")
StageParsers.updateEventNames()
# gf.exportGatya()
# sf.exportStages()
# print("hello")
