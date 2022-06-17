import csv
from collections import defaultdict

import pandas as pd
from src_extractors.base import config
from src_backend.local_readers import Readers

blacklist = {"Speed Up", "Treasure Radar", "Rich Cat", "Cat Jobs", "Sniper the Cat", "Cat CPU", "Unknown", "Nothing"}

def extract():
	flnames_jp = config['inputs']['jp']['stamps']['data']
	
	print("Started extracting stamps")
	
	with open(flnames_jp, encoding='utf-8', newline='') as fl:
		stamps = [[int(cell) for cell in stamp] for stamp in list(csv.reader(fl))]
	
	stamp_text = ""
	stamp_dist_text = ""
	for stamp in stamps:
		ID = stamp[0]
		drop_head = 5
		drops = []
		qty_dist = defaultdict(lambda: 0)
		
		while drop_head < len(stamp):
			item_count = stamp[drop_head]
			item_head = drop_head + 2
			drop_head += 2 + 3 * item_count
			drop_items = []
			
			while item_head < drop_head:
				is_unit = stamp[item_head]
				item_id = stamp[item_head + 1]
				item_qty = stamp[item_head + 2]
				
				if is_unit == 1:
					toput = Readers.getCat(item_id, form=0)
				elif is_unit == 0:
					toput = Readers.getItem(item_id)
				elif is_unit == -1:
					toput = "Nothing"
				else:
					raise AssertionError
				
				if toput not in blacklist:
					qty_dist[toput] += item_qty
					
				drop_items.append(f"{toput}{' X ' + str(item_qty) if item_qty > 1 else ''}")
				item_head += 3
			drops.append(', '.join(drop_items))
		stamp_text += f"{ID}\t"+'|'.join(drops)+"\n"
		stamp_dist_text += f"{ID}\t"+'|'.join(
			[f"{k}" + (f" X {v}" if v > 1 else "") for k, v in sorted(qty_dist.items())])+"\n"
		
		with open(config['outputs']['stamps'], encoding='utf-8', newline='', mode='w') as fl:
			fl.write(stamp_text+"\n\n"+stamp_dist_text)
				
	print("Finished extracting stamps")

if __name__ == "__main__":
	extract()
