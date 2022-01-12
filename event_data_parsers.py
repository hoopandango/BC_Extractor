import datetime
import json

import numpy as np
import pandas as pd

from containers import Gatya
from event_data_parsers_universal import UniversalParsers
from local_readers import Readers
from z_downloaders import Downloaders

with open('_config.json') as fl:
	config = json.load(fl)


class GatyaParsers(UniversalParsers):
	def __init__(self):
		UniversalParsers.__init__(self)
	
	gatyaLocal = pd.read_json(config["outputs"]["gatya_json"], orient='index')
	
	@staticmethod
	def getCategory(banner: list[str]) -> str:
		# tells which category of capsule is in this banner
		p = banner[8]
		if p == "0":
			return "Cat Capsule"  # Normal, lucky, G, catseye, catfruit, etc : uses GatyaDataSetN1.csv
		if p == "1":
			return "Rare Capsule"  # Rare, platinum : uses GatyaDataSetR1.csv
		
		return "Event Capsule"  # bikkuri, etc.
	
	@staticmethod
	def getValueAtOffset(banner: list[str], i: int) -> str:
		slot: int = int(banner[9]) - 1
		# each slot is 15 columns wide
		offset: int = 15 * slot
		return banner[i + offset]
	
	@staticmethod
	def getGatyaRates(banner: list[str]) -> list[int]:
		rates: list[int] = []
		for i in range(5):
			rates.append(int(GatyaParsers.getValueAtOffset(banner, 14 + 2 * i)))  # 14,16,18,20,22
		return rates
	
	@staticmethod
	def getGuarantees(banner: list[str]) -> list[bool]:
		G: list[bool] = []
		for i in range(5):
			G.append(GatyaParsers.getValueAtOffset(banner, 15 + 2 * i) == '1')  # 15,17,19,21,23
		return G
	
	@classmethod
	def appendGatyaLocal(cls, gatya: Gatya) -> None:
		toret = {"name": "Unknown", "exclusives": [], "rate_ups": {}, "diff": [[], []]}
		
		if (gatya.page == "Rare Capsule"):
			try:
				obj = cls.gatyaLocal.loc[gatya.ID].to_dict()
				toret["name"] = obj["banner_name"]
				toret["exclusives"] = obj["exclusives"]
				toret["rate_ups"] = obj["rate_ups"]
				toret["diff"] = obj["diff"]
			except KeyError:
				pass
		
		else:
			# set to unknown if not found
			requested = Downloaders.requestGatya(gatya.ID, 'en', gatya.page)
			if requested.startswith("Request Failed"):
				requested = "Unknown"
			toret["name"] = requested
		
		gatya.name = toret["name"]
		gatya.exclusives = toret["exclusives"]
		gatya.rate_ups = toret["rate_ups"]
		gatya.diff = toret["diff"]
	
	@classmethod
	def getExtras(cls, banner: list[str]) -> list[str]:
		toret = []
		extras = int(cls.getValueAtOffset(banner, 13))
		severID = (extras >> 4) & 1023
		
		if extras & 4:
			toret.append('SU')  # Step-up
		if extras & 16384:
			toret.append('PS')  # Platinum Shard
		
		if not extras & 8:
			return toret  # No item drops
		# if it has item drops:
		item = Readers.getItemBySever(severID)
		if item == 'Lucky Ticket':
			toret.append('L')  # Has lucky ticket
		return toret
	
	@staticmethod
	def getString(banner: Gatya) -> tuple[str, str]:
		# tuple (datestring, reststring)
		bonuses: list[str] = []
		
		if banner.guarantee[3] == 1:  bonuses.append('G')
		bonuses.extend(banner.extras)
		bonuses.extend([x for x in banner.exclusives if x != 'D'])
		bonusesStr: str = f" [{'/'.join(bonuses)}]" if len(bonuses) > 0 else ''
		
		diff: str = f' (+ {", ".join(banner.diff[0])})' if 5 > len(banner.diff[0]) > 0 else ''
		
		rate_ups: str = " {" + ", ".join([f"{K}x rate on {', '.join(V)}" for (K, V) in banner.rate_ups.items()]) + "}" \
			if len(banner.rate_ups) > 0 else ''
		
		name = banner.name if banner.name != 'Unknown' else banner.text
		return (GatyaParsers.fancyDate(banner.dates), '%s%s%s%s' % (name, bonusesStr, diff, rate_ups))

class StageParsers(UniversalParsers):
	def __init__(self):
		UniversalParsers.__init__(self)
	
	@staticmethod
	def formatTime(t: str) -> datetime.time:
		if t == "2400":
			t = "2359"
		if t == "0":
			t = "0000"
		if len(t) == 3:  # fixes time if hour is < 10am
			t = '0' + t
		dt = datetime.datetime.strptime(t, '%H%M')
		return datetime.time(dt.hour, dt.minute)
	
	@staticmethod
	def formatMDHM(s: str, t: str) -> datetime.datetime:
		if t == "2400":
			t = "2359"
		if t == "0":
			t = "0000"
		if len(s) == 3:  # fixes date if month isn't nov or dec
			s = '0' + s
		
		return datetime.datetime.strptime(s + t, '%m%d%H%M')
	
	@staticmethod
	def binaryweekday(N: int) -> list[int]:
		list_to_return: list[int] = [int(x) for x in list(bin(N))[2:][::-1]]
		while len(list_to_return) < 7:
			list_to_return.append(0)
		return list_to_return
	
	@classmethod
	def yearly(cls, data: list[str]) -> tuple[list[dict[str, list[dict[str, datetime.datetime]]]], list[int]]:
		numberOfPeriods: int = int(data[7])
		n: int = 8
		output: list[dict[str, list[dict[str, datetime.datetime]]]] = [dict() for _ in range(numberOfPeriods)]
		IDs: list[int] = []
		for i in range(numberOfPeriods):
			
			times, n = int(data[n]), n + 1
			output[i]["times"] = [dict() for _ in range(times)]
			
			for j in range(times):
				startDate, n = data[n], n + 1
				startTime, n = data[n], n + 1
				endDate, n = data[n], n + 1
				endTime, n = data[n], n + 1
				output[i]["times"][j]["start"] = cls.formatMDHM(startDate, startTime)
				output[i]["times"][j]["end"] = cls.formatMDHM(endDate, endTime)
				if output[i]["times"][j]["end"] < output[i]["times"][j]["start"]:
					# this means the event ends the next year, like it starts on christmas and lasts for 2 weeks
					output[i]["times"][j]["end"] = output[i]["times"][j]["end"].replace(year=1901)
			
			n = n + 3  # trailing zeros
		
		nIDs, n = int(data[n]), n + 1
		for k in range(max(nIDs, 1)):
			ID, n = int(data[n]), n + 1
			if nIDs > 0:
				IDs.append(ID)
		
		return output, IDs
	
	@classmethod
	def monthly(cls, data: list[str]) -> tuple[list[dict[str, list[str | dict[str, datetime.datetime]]]], list[int]]:
		numberOfPeriods: int = int(data[7])
		n: int = 9
		output: list[dict[str, list[str | dict[str, datetime.time]]]] = [dict() for _ in range(numberOfPeriods)]
		IDs = []
		for i in range(numberOfPeriods):
			
			dates, n = int(data[n]), n + 1
			output[i]["dates"] = [""] * int(dates)
			for u in range(int(dates)):
				output[i]["dates"][u], n = data[n], n + 1
			
			n = n + 1  # Trailing zero
			
			times, n = int(data[n]), n + 1
			output[i]["times"] = [dict() for _ in range(times)]
			
			for j in range(times):
				start, n = data[n], n + 1
				end, n = data[n], n + 1
				output[i]["times"][j]["start"] = cls.formatTime(start)
				output[i]["times"][j]["end"] = cls.formatTime(end)
			
			nIDs, n = int(data[n]), n + 1
			for k in range(nIDs):
				ID, n = int(data[n]), n + 1
				if nIDs > 0:
					IDs.append(ID)
		
		return output, IDs
	
	@classmethod
	def weekly(cls, data: list[str]) -> tuple[list[dict[str, list[int | dict[str, datetime.time]]]], list[int]]:
		numberOfPeriods: int = int(data[7])
		n: int = 10
		output: list[dict[str, list[int | dict[str, datetime.time]]]] = [dict() for _ in range(numberOfPeriods)]
		IDs: list[int] = []
		for i in range(numberOfPeriods):
			
			weekdays, n = cls.binaryweekday(int(data[n])), n + 1
			output[i]["weekdays"] = weekdays
			times, n = int(data[n]), n + 1
			output[i]["times"] = [dict() for _ in range(times)]
			
			for j in range(times):
				start, n = data[n], n + 1
				end, n = data[n], n + 1
				output[i]["times"][j]["start"] = cls.formatTime(start)
				output[i]["times"][j]["end"] = cls.formatTime(end)
			
			nIDs, n = int(data[n]), n + 1
			
			for k in range(max(nIDs, 1)):
				ID, n = int(data[n]), n + 1
				if nIDs > 0:
					IDs.append(ID)
		
		return output, IDs
	
	@classmethod
	def daily(cls, data: list[str]) -> tuple[list[dict[str, list[dict[str, datetime.time]]]], list[int]]:
		numberOfPeriods: int = int(data[7])
		n: int = 11
		output: list[dict[str, list[dict[str, datetime.time]]]] = [dict() for _ in range(numberOfPeriods)]
		IDs = []
		for i in range(numberOfPeriods):
			
			times, n = int(data[n]), n + 1
			output[i]["times"] = [dict() for _ in range(times)]
			
			for j in range(times):
				startTime, n = data[n], n + 1
				endTime, n = data[n], n + 1
				output[i]["times"][j]["start"] = cls.formatTime(startTime)
				output[i]["times"][j]["end"] = cls.formatTime(endTime)
		
		nIDs, n = int(data[n]), n + 1
		for k in range(max(nIDs, 1)):
			ID, n = int(data[n]), n + 1
			if nIDs > 0:
				IDs.append(ID)
		
		return output, IDs
	
	@staticmethod
	def interpretDates(dates: np.array) -> tuple[int, int, int]:
		# takes in dates array and the number of days in the month in which they start
		# returns a 3-tuple -> (group_size, starting_date, ending_date)
		if len(dates) <= 4:  # don't group these
			return (0, 0, 0)
		diffs = list(np.diff(dates))
		mode = max(set(diffs), key=diffs.count)
		outliers = [i for i, x in enumerate(diffs) if x != mode]
		if len(outliers) > 1:
			# there can be at most one gap in any patterned data
			return (0, 0, 0)
		elif len(outliers) == 0:
			# there is no gap, assume all events to be happening in the same month
			return (mode, min(dates), max(dates))
		else:
			# there is a gap, repetition started after it and ended at it
			# a better algorithm would check whether or not there is an actual rollover
			# taking in the number of days in the month as a parameter
			return (mode, dates[outliers[0] + 1], dates[outliers[0]])
		# this algorithm ignores month rollover diff [-1->0], and can give false positives, but they are not expected

class ItemParsers(UniversalParsers):
	def __init__(self):
		UniversalParsers.__init__(self)

class MissionParsers(UniversalParsers):
	def __init__(self):
		UniversalParsers.__init__(self)
