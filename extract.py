import os
import json
import zipfile
import extraction.decrypt as dcrypt
import shutil
import src_extractors

PATH = "../../../Downloads/"
with open("_config.json") as fl:
	config = json.load(fl)

def fetch():
	LNG = input("enter language (en / jp)")
	for file in os.listdir(PATH):
		if file.endswith(".apk"):
			topull = []
			
			for category in config["inputs"][LNG].values():
				for filename in category.values():
					topull.append(filename.split('/')[-1])
					
			os.mkdir("extraction/temp")
			os.rename(PATH+file, "extraction/temp/apk.zip")
			
			with zipfile.ZipFile("extraction/temp/apk.zip", "r") as zip_ref:
				for template in ["DataLocal", "resLocal"]:
					zip_ref.extract(f"assets/{template}.list", "extraction/temp")
					zip_ref.extract(f"assets/{template}.pack", "extraction/temp")
				dcrypt.pull_out_files(topull, "temp", LNG)
			
			try:
				shutil.rmtree(f"latest_{LNG}")
			except KeyError:
				pass
			shutil.move(src=f"extraction/temp/latest_{LNG}", dst=f"latest_{LNG}", copy_function=shutil.copytree)
			shutil.rmtree("extraction/temp")
			break
			
# fetch()
src_extractors.run_all()
