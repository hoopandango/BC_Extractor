from __future__ import annotations

import datetime
from dataclasses import dataclass

from .event_data_parsers import UniversalParsers

class Colourer:
	ENABLED: bool = False
	
	def enable(self):
		self.ENABLED = True
	
	def clc(self, text: str, code: int) -> str:
		if not self.ENABLED:
			return text
		else:
			return f"[0m[{code}m{text}[0m"

@dataclass
class Event:
	ID: int = None
	dates: list[datetime.datetime] = None
	versions: tuple[int] = None
	name: str = None
	clr: Colourer = Colourer()
	
	def __str__(self) -> str:
		return self.clr.clc(UniversalParsers.fancyDate(self.dates), 34) + self.name
	
	def package(self):
		toret = self.__dict__.copy()
		toret["printable"] = str(self)
		return toret

@dataclass
class EventGroup:
	name: str
	events: list[Event]
	dates: list[datetime.datetime]
	split: bool
	visible: bool
	
	def __str__(self) -> str:
		if self.split:
			if isinstance(self.events[0], Gatya):
				for i in range(len(self.events) - 1):
					if self.events[i].dates[1] > self.events[i + 1].dates[0]:
						self.events[i].dates[1] = self.events[i + 1].dates[0]
			return '\n'.join([str(x) for x in self.events])
		else:
			return self.events[0].clr.clc(UniversalParsers.fancyDate(self.dates), 34) + self.name
	
	def package(self):
		toret = self.__dict__.copy()
		toret["events"] = [X.package() for X in self.events]
		toret["printable"] = str(self)
		return toret

@dataclass
class Gatya(Event):
	rates: list[int] = None
	rate_ups: dict[str, int] = None
	diff: list[list[str]] = None
	page: str = None
	slot: int = None
	guarantee: list[bool] = None
	extras: list[str] = None
	exclusives: list[str] = None
	text: str = None
	
	def __text_form(self) -> tuple[str, str]:
		# tuple (datestring, reststring)
		bonuses: list[str] = []
		bonusesStr: str = ""
		if self.guarantee[3] == 1:  bonusesStr += self.clr.clc(' (Guaranteed)', 31)
		bonuses.extend(self.extras)
		bonuses.extend([x for x in self.exclusives])
		if self.rates[3] == 1000:  bonuses.append('+')
		bonusesStr += f" [{'/'.join(bonuses)}]" if len(bonuses) > 0 else ''
		
		diff: str = f' (+ {", ".join(self.diff[0])})' if 5 > len(self.diff[0]) > 0 else ''
		
		rate_ups: str = " {{" + ", ".join([f"{K}x rate on {', '.join(V)}" for (K, V) in self.rate_ups.items()]) + "}}" \
			if len(self.rate_ups) > 0 else ''
		
		name = self.name if self.name != 'Unknown' else self.text
		
		if not self.clr.ENABLED and self.guarantee[3]:
			pre = "--"
		else:
			pre = ""
		return (pre+UniversalParsers.fancyDate(self.dates), '%s%s%s%s' % (name, bonusesStr, diff, rate_ups))
	
	def __str__(self):
		self.dates = [self.dates[0], self.dates[-1]]
		return (f"{self.clr.clc('%s', 34)}%s" % self.__text_form()).format(oldyear=self.dates[0].year,
		                                                                  newyear=self.dates[-1].year)

@dataclass
class Stage(Event):
	sched: str = None
	sched_data: dict = None
	
	@classmethod
	def fromEvent(cls, e: Event) -> Stage:
		return cls(**e.__dict__)
	
	@classmethod
	def fromItem(cls, i: Item) -> Stage:
		return cls(ID=i.ID, dates=i.dates, versions=i.versions, name=i.name)
	
	def package(self):
		toret = self.__dict__.copy()
		toret["printable"] = str(self)
		return toret

@dataclass
class Sale(Event):
	@classmethod
	def fromEvent(cls, e: Event) -> Sale:
		toret = cls()
		toret.__dict__ = {K: e.__dict__[K] for K in toret.__dict__.keys() & e.__dict__.keys()}
		return toret

@dataclass
class Mission(Event):
	@classmethod
	def fromEvent(cls, e: Event) -> Mission:
		toret = cls()
		toret.__dict__ = {K: e.__dict__[K] for K in toret.__dict__.keys() & e.__dict__.keys()}
		return toret

@dataclass
class Item(Event):
	recurring: bool = False
	qty: int = 0
	text: str = None
	
	@classmethod
	def fromEvent(cls, e: Event) -> Item:
		return cls(**e.__dict__)
	
	def __str__(self):
		q = (' x ' + str(self.qty)) if self.qty > 1 else ''
		if self.name in ['Cat Food', 'Rare Ticket'] and (self.dates[1] - self.dates[0]).days >= 2:
			q += ' (Daily)' if self.recurring else ' (Only Once)'
		if self.name == 'Rare Ticket':
			q += " - " + self.text
		return f"{self.clr.clc(UniversalParsers.fancyDate(self.dates), 34)}" + self.name + q
	
@dataclass
class RawEventGroup(Event):
	IDs: list[int] = None
	sched: str = None
	sched_data: dict = None
	
	@classmethod
	def makeSingleton(cls, e: Event) -> RawEventGroup:
		toret: RawEventGroup = RawEventGroup(**e.__dict__)
		toret.IDs = [e.ID]
		return toret
